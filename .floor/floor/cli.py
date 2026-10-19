"""Command line: python -m floor <command>."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import wave
from pathlib import Path

import requests

from . import __version__
from . import (attest, backtest, delta_m, energy, fallback, footprint, h1, judge, manifest, memory, meter, notice,
               herald, offline, page, paths, policy, qemu, ratchet, release, spotcheck)
from .isa.levels import level_name
from .isa.scan import ROLES, FileReport, scan_path, summarize
from .oci import DEFAULT_REPO, Registry, inspect_image, pull_layer


def _write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")


def _print_rows(rows: list[tuple[str, ...]]) -> None:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]) - 1)]
    for row in rows:
        print("  ".join(f"{cell:<{width}}" for cell, width in zip(row, widths)) + "  " + row[-1])


def _cmd_scan(args: argparse.Namespace) -> int:
    reports: list[FileReport] = []
    for path in args.paths:
        if not Path(path).exists():
            print(f"floor: no such file or directory: {path}", file=sys.stderr)
            return 2
        reports.extend(scan_path(path, role=args.role))
    if not reports:
        print("floor: no x86-64 ELF files found", file=sys.stderr)
        return 2
    summary = summarize(reports)
    if args.json:
        _write_json(Path(args.json), {"tool": f"floor {__version__}", "summary": summary,
                                      "files": [r.to_dict() for r in reports]})
    if not args.quiet:
        _print_table(reports, summary)
    return 0


def _cmd_image(args: argparse.Namespace) -> int:
    registry = Registry(args.repo)
    rows = [("REF", "CREATED", "FLOOR", "HIGHEST", "EXTRAS")]
    failed = False
    for ref in args.refs:
        try:
            info, layer = inspect_image(registry, ref)
            folder = pull_layer(registry, layer)
        except (requests.RequestException, LookupError, NotImplementedError, ValueError) as exc:
            print(f"floor: {ref}: {exc}", file=sys.stderr)
            rows.append((ref, "-", "error", "-", "-"))
            failed = True
            continue
        reports = scan_path(folder)
        summary = summarize(reports)
        if args.out:
            name = re.sub(r"[^A-Za-z0-9._-]", "_", ref)
            _write_json(Path(args.out) / f"{name}.json", {"tool": f"floor {__version__}", "image": info,
                                                         "summary": summary, "files": [r.to_dict() for r in reports]})
        if args.verbose:
            print(f"== {ref}")
            _print_table(reports, summary)
            print()
        floor = summary["floor"]
        rows.append((ref, (info["created"] or "-")[:19], floor["level"], summary["highest_level_found"],
                     ",".join(floor["extras"]) or "-"))
    _print_rows(rows)
    return 1 if failed else 0


def _cmd_sample(args: argparse.Namespace) -> int:
    tags = backtest.main_tags(Registry(args.repo).tags(), args.prefix)
    dated = backtest.image_dates(tags, args.repo)
    around = [backtest.parse_around(text) for text in args.around] if args.around else \
        [backtest.parse_around(f"{day}:{label}") for day, label in backtest.DEFAULT_AROUND]
    chosen = backtest.choose(dated, args.count, around, args.window_days)
    refs = [item["ref"] for item in chosen]
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", "repo": args.repo, "main_tags": len(tags),
                                     "undated": sorted(ref for ref, created in dated.items() if not created),
                                     "images": chosen, "batches": backtest.batches(refs, args.batch)})
    for item in chosen:
        print(f"{item['ref']}  {(item['created'] or '-')[:19]}  {', '.join(item['reasons'])}", file=sys.stderr)
    for batch in backtest.batches(refs, args.batch):
        print(" ".join(batch))
    return 0 if chosen else 2


def _cmd_timeline(args: argparse.Namespace) -> int:
    rows = backtest.timeline(args.paths)
    if not rows:
        print("floor: no image reports found", file=sys.stderr)
        return 2
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", "images": rows})
    _print_rows([("CREATED", "FLOOR", "HIGHEST", "VARIANT", "REF", "EXTRAS")] + [
        ((row["created"] or "-")[:19], row["floor"], row["highest_level_found"], row["baseline_variant"] or "-",
         row["ref"], ",".join(row["extras"]) or "-") for row in rows])
    return 0


def _cmd_backtest_footprint(args: argparse.Namespace) -> int:
    registry = Registry(args.repo)
    result = backtest.footprint({Path(path).name: _load_timeline(path) for path in args.timelines},
                                [_read_json(path) for path in args.runs],
                                lambda digest: backtest.download_sizes(registry, digest))
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", "repo": args.repo, **result})
    print(f"Images: {result['images']}  downloaded: {result['download_mb']} MB  "
          f"runner time: {result['runner_minutes']} min in {len(result['runs'])} run(s)")
    return 0


def _cmd_spotcheck(args: argparse.Namespace) -> int:
    result = spotcheck.summary(_read_json(args.labels))
    print(spotcheck.text(result))
    return 0


def _load_timeline(path: str) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))["images"]


def _cmd_h1(args: argparse.Namespace) -> int:
    rows = _load_timeline(args.timeline)
    result = h1.analyse(rows, args.git)
    if args.pair:
        other = _load_timeline(args.pair)
        pairs = h1.same_commit_pairs(rows, other)
        shared = h1.shared_commits(rows, other)
        result["pair_timeline"] = args.pair
        result["shared_commits"] = shared
        result["same_commit_different_floor"] = pairs
        result["pair_verdict"] = h1.pair_verdict(pairs, shared)
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", "timeline": args.timeline, **result})
    print(f"Images: {result['images']}  {result['levels']}")
    print(f"Flips: {result['flips']}  without a change in the floor paths: {result['flips_without_floor_path_changes']}")
    for flip in result["details"]:
        changes = flip["floor_path_changes"]
        note = "not checked" if changes is None else (", ".join(changes[:4]) or "no change")
        print(f"  {flip['from']['created'][:16]} {flip['from']['floor']} -> {flip['to']['created'][:16]} "
              f"{flip['to']['floor']}  {flip['to']['ref'][:13]}  {note}")
    for pair in result.get("same_commit_different_floor", []):
        print(f"  same commit {pair['commit'][:8]}: {pair['a_floor']} ({pair['a'][:-41]}) vs "
              f"{pair['b_floor']} ({pair['b'][:-41]})")
    print(f"Verdict (flips): {result['verdict']}")
    if "pair_verdict" in result:
        print(f"Verdict (same commit): {result['pair_verdict']}")
    return 0


def _cmd_probe(args: argparse.Namespace) -> int:
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not cmd:
        print("floor: give the command after --", file=sys.stderr)
        return 2
    env = dict(item.split("=", 1) for item in args.env or [])
    try:
        result = qemu.probe(cmd, tuple(args.cpu or qemu.DEFAULT_MODELS), expect=args.expect,
                            sysroot=args.sysroot, timeout=args.timeout, env=env)
    except FileNotFoundError as exc:
        print(f"floor: {exc}", file=sys.stderr)
        return 2
    result["label"] = args.label
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", **result})
    if args.sysroot:
        print(f"sysroot {args.sysroot}: {result['sysroot_links_rewritten']} absolute link(s) made relative")
    rows = [("CPU", "LEVEL", "RESULT", "EXIT", "SIGNAL", "VARIANT", "CONTROLS")]
    for run in result["runs"]:
        ctl = run["controls"]
        rows.append((run["cpu"], run["cpu_level"], run["result"], str(run["exit"]), run["signal"] or "-",
                     run["loaded_variant"] or "-",
                     f"+v{ctl['positive']['level']}:{ctl['positive']['result']} -v{ctl['negative']['level']}:{ctl['negative']['result']}"))
    _print_rows(rows)
    return 0


def _cmd_policy(args: argparse.Namespace) -> int:
    try:
        doc = policy.load(args.file, args.schema)
    except (OSError, policy.PolicyError) as exc:
        print(f"floor: policy not valid: {exc}", file=sys.stderr)
        return 1
    if args.artifact:
        print(json.dumps(policy.for_artifact(doc, args.artifact), indent=2))
    else:
        artifacts = ", ".join(sorted(doc.get("artifacts") or {})) or "none"
        print(f"{args.file}: valid (CPU floor {doc['cpu']['x86_64_min_level']}, per-artifact entries: {artifacts})")
    return 0


def _cmd_ratchet(args: argparse.Namespace) -> int:
    try:
        new = policy.load(args.new)
        if args.base:
            old, notices = ratchet.from_git(args.base)
        elif args.old:
            old, notices = policy.load(args.old), ratchet.from_dir(args.notices)
        else:
            print("floor: give --base REF or --old FILE", file=sys.stderr)
            return 2
    except (OSError, policy.PolicyError, ValueError) as exc:
        print(f"floor: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"floor: git failed: {exc.stderr.strip()}", file=sys.stderr)
        return 2
    verify = None
    if args.approvals:
        if not (args.base and args.default_branch):
            print("floor: --approvals needs --base and --default-branch", file=sys.stderr)
            return 2
        session = requests.Session()

        def get(path: str):
            resp = session.get(args.approvals.rstrip("/") + path, timeout=30)
            resp.raise_for_status()
            return resp.json()
        humans = (args.humans if args.humans is not None else os.environ.get("FLOOR_HUMANS", "")).split()
        verify = ratchet.approval(args.base, args.default_branch, get, humans)
    result = ratchet.check(old, new, notices, verify)
    for row in result["changes"]:
        scope = f"{row['artifact']}: " if row["artifact"] else ""
        cover = ""
        if row["direction"] == "looser":
            cover = f" (notice: {', '.join(row['notices'])})" if row["notices"] else " NEEDS A MERGED NOTICE"
        print(f"{scope}{row['field']}: {row['from']} -> {row['to']}: {row['direction']}{cover}")
        for name, problems in (row.get("refused") or {}).items():
            for problem in problems:
                print(f"  {name} does not count: {problem}")
    if not result["changes"]:
        print("policy floors did not change")
    return 0 if result["ok"] else 1


def _cmd_notice(args: argparse.Namespace) -> int:
    failed = 0
    for path in args.files:
        if Path(path).name == "README.md":
            continue
        found = notice.problems(Path(path).read_text(encoding="utf-8"), draft=args.draft)
        print(f"{path}: {'complete' if not found else '; '.join(found)}")
        failed += bool(found)
    return 1 if failed else 0


def _cmd_notice_draft(args: argparse.Namespace) -> int:
    try:
        verdict = _read_json(args.judge)
        doc = policy.for_artifact(policy.load(args.policy), verdict.get("artifact"))
        diagnosis = Path(args.diagnosis).read_text(encoding="utf-8") if args.diagnosis else ""
    except (OSError, ValueError, policy.PolicyError) as exc:
        print(f"floor: {exc}", file=sys.stderr)
        return 2
    dimensions = verdict.get("missing_notice") or []
    if not dimensions:
        print(f"no draft: no floor needs a new Leave-Behind Notice (decision: {verdict.get('decision')})")
        return 0
    flags = None
    if (doc.get("repair") or {}).get("fallback", "canned_inclusive_config") == "canned_inclusive_config":
        todo = fallback.pending(args.root, artifact=verdict.get("artifact") or "main")
        if todo:
            print(f"no draft: the canned inclusive config is not on this branch yet ({', '.join(todo)}). "
                  "The fallback runs first (F4.3).")
            return 0
        flags = fallback.flags_text()
    scenarios = {}
    for path in sorted(Path(args.scenarios).glob("*.yml")):
        if path.name == "TEMPLATE.yml":
            continue
        try:
            scenario = delta_m.load(path)
        except (OSError, delta_m.ScenarioError) as exc:
            print(f"{path.as_posix()}: not used: {exc}")
            continue
        if scenario.get("dimension") in dimensions:
            scenarios[path.as_posix()] = delta_m.compute(scenario)
    text = notice.draft(verdict, doc, diagnosis=diagnosis, truncated=args.truncated, mr=args.mr,
                        evidence=args.evidence, flags=flags, scenarios=scenarios)
    name = notice.next_name([p.name for p in Path(args.notices).glob("*.md")], dimensions)
    out = Path(args.out) / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    fill = [found.split(":")[0] for found in notice.problems(text, draft=True)] + ["Approved by"]
    print(text)
    print(f"wrote {out.as_posix()}, a draft. A code owner fills: {', '.join(fill)}.")
    print("The repair loop stops here (F4.5). To accept the change, add the draft as "
          f"{Path(args.notices).as_posix()}/{name} in a new MR (template: Leave-Behind-Notice), fill those fields "
          "and approve the MR as a code owner. To refuse it, close the MR.")
    return 0


def _cmd_paths(args: argparse.Namespace) -> int:
    actor = args.actor
    if actor == "auto":  # a CI job: the pipeline user and the MR author decide (D-014)
        actor, reasons = paths.pipeline_actor(os.environ)
        for line in reasons:
            print(line)
        if actor == "human":
            print("human: code-owner review applies, not the agent allowlist")
            return 0
    try:
        changed = args.files or paths.changed_files(args.base)
    except subprocess.CalledProcessError as exc:
        print(f"floor: git failed: {exc.stderr.strip()}", file=sys.stderr)
        return 2
    found = paths.check(changed, actor)
    for line in found:
        print(line)
    print(f"{len(changed)} changed path(s); {actor}: {'allowed' if not found else 'NOT allowed'}")
    return 1 if found else 0


def _cmd_fallback(args: argparse.Namespace) -> int:
    if args.judge:
        try:
            verdict = _read_json(args.judge)
            doc = policy.for_artifact(policy.load(args.policy), verdict.get("artifact"))
        except (OSError, ValueError, policy.PolicyError) as exc:
            print(f"floor: {exc}", file=sys.stderr)
            return 2
        if verdict.get("decision") != "fail":
            print(f"no fallback: the gate did not fail (decision: {verdict.get('decision')})")
            return 0
        if (doc.get("repair") or {}).get("fallback", "canned_inclusive_config") != "canned_inclusive_config":
            print("no fallback: the policy has no canned config (repair.fallback)")
            return 0
    if args.patch:
        text = fallback.patch(args.root, args.dockerfile, args.artifact)
        if not text:
            print("canned config already applied: no patch. floor notice-draft runs next (F4.5)")
            return 0
        out = Path(args.patch)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out.as_posix()}: commit it to the branch with git apply (F4.3). Canned config: {fallback.flags_text()}")
        return 0
    changed = fallback.apply(args.root, args.dockerfile, args.artifact)
    for path in changed:
        print(f"changed {path}")
    print(f"canned config: {fallback.flags_text()}" if changed else "canned config already applied")
    return 0


def _cmd_page(args: argparse.Namespace) -> int:
    print(f"wrote {page.build(args.evidence, args.out, args.notices)}")
    return 0


def _cmd_delta_m(args: argparse.Namespace) -> int:
    try:
        scenario = delta_m.load(args.scenario)
    except (OSError, delta_m.ScenarioError) as exc:
        print(f"floor: scenario not valid: {exc}", file=sys.stderr)
        return 2
    verdict = _read_json(args.judge)
    held = bool(verdict) and verdict.get("pareto") in ("held", "inclusive")
    result = delta_m.compute(scenario, floors_held=held)
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", **result})
    print(delta_m.markdown(result), end="")
    return 0


def _read_json(path: str | None) -> dict | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def _g(value) -> str:
    return "-" if value is None else f"{value:.4g}"


def _cmd_footprint(args: argparse.Namespace) -> int:
    if args.action == "check":
        if not args.files:
            print("floor: give the if-run output files", file=sys.stderr)
            return 2
        rows, problems = [], []
        for path in args.files:
            found_rows, found = footprint.check_file(path)
            rows += found_rows
            problems += found
        summary = footprint.summarize(rows)
        if args.expect:
            problems += footprint.differences(summary, _read_json(args.expect) if Path(args.expect).exists() else None)
        if args.out:
            _write_json(Path(args.out), {"tool": f"floor {__version__}", **summary})
        if rows:
            _print_rows([("MANIFEST", "CHILD", "REGION", "ENERGY_KWH", "CARBON_G", "SCI_G")] + [
                (r["manifest"] or "-", r["child"] + (" (headline)" if r["headline"] else ""), r["region"] or "-",
                 _g(r["energy_kwh"]), _g(r["carbon_gco2e"]), _g(r["sci_gco2e"])) for r in rows])
        for line in problems:
            print(line)
        print(f"{len(rows)} result(s): {'every output matches the formulas' if not problems else f'{len(problems)} problem(s)'}")
        return 1 if problems or not rows else 0
    energy, meter = (_read_json(p) if p and Path(p).exists() else None for p in (args.energy, args.meter))
    files = footprint.write(footprint.load(args.config), energy, meter)
    out_dir = Path(args.out_dir)
    if args.action == "stale":
        found = footprint.stale(files, out_dir)
        for line in found:
            print(line)
        print(f"{len(files)} manifest(s): {'up to date' if not found else 'STALE: run floor footprint write'}")
        return 1 if found else 0
    if not files:
        print("floor: no energy or meter evidence, so no manifest", file=sys.stderr)
    for name, text in files.items():
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {out_dir / name}")
    return 0


def _previous_floors(doc: dict | None) -> dict | None:
    """Accepts a manifest (floors under "predicate") or a judge output."""
    if not doc:
        return None
    return (doc.get("predicate") or doc).get("floors")


def _cmd_manifest(args: argparse.Namespace) -> int:
    floor_evidence = {}
    for item in args.floor_evidence or []:
        name, _, url = item.partition("=")
        if not name or not url:
            print(f"floor: --floor-evidence needs FLOOR=URL, not {item!r}", file=sys.stderr)
            return 2
        floor_evidence[name] = url
    verdict = _read_json(args.judge)
    scan = _read_json(args.scan)
    previous = _read_json(args.previous)
    doc = manifest.build(verdict, subject=args.subject, digest=args.digest, release=args.release, commit=args.commit,
                         scan=scan["summary"] if scan else None, cmake_flags=args.cmake_flags,
                         base_image=args.base_image, build_cpu=args.build_cpu, previous=previous, evidence=args.evidence,
                         fixed_by=args.fixed_by, notices=args.notice, project_url=args.project_url,
                         delta_m=_read_json(args.delta_m), footprint=_read_json(args.footprint),
                         floor_evidence=floor_evidence)
    _write_json(Path(args.out), doc)
    text = manifest.diff_markdown(previous, doc)
    if args.diff:
        Path(args.diff).write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    print(manifest.diff_markdown(_read_json(args.old), _read_json(args.new)), end="")
    return 0


def _cmd_attest(args: argparse.Namespace) -> int:
    try:
        if args.action == "identity":
            token = os.environ.get(args.token_env)
            if not token:
                raise ValueError(f"no ID token in ${args.token_env} (id_tokens in .gitlab-ci.yml)")
            print(attest.identity(token))
            return 0
        if not args.manifest:
            raise ValueError(f"floor attest {args.action} needs --manifest")
        statement = _read_json(args.manifest)
        if args.action == "predicate":
            if not args.out:
                raise ValueError("floor attest predicate needs --out")
            kind, pred = attest.predicate(statement)
            _write_json(Path(args.out), pred)
            print(kind)
            return 0
        if not args.verified:
            raise ValueError("floor attest check needs --verified")
        problem = attest.check(statement, Path(args.verified).read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        print(f"floor: {exc}", file=sys.stderr)
        return 2
    if problem:
        print(f"attestation: FAIL: {problem}")
        return 1
    print(f"attestation: verified, same predicate as the manifest on {statement['subject'][0]['name']}@sha256:"
          f"{statement['subject'][0]['digest']['sha256']}")
    return 0


def _cmd_release(args: argparse.Namespace) -> int:
    session = requests.Session()
    project = f"{args.api.rstrip('/')}/projects/{args.project}"

    def get(path: str):
        resp = session.get(project + path, timeout=30)
        resp.raise_for_status()
        return resp.json()

    links = []
    for item in args.link or []:
        name, _, url = item.partition("=")
        if not name or not url.startswith("https://"):
            print(f"floor: --link needs NAME=https://..., not {item!r}", file=sys.stderr)
            return 2
        links.append({"name": name, "url": url})
    try:
        plan = release.plan(args.sha, args.default_branch, get)
        if "skip" in plan:
            print(f"no release: {plan['skip']}")
            return 0
        diff = Path(args.diff).read_text(encoding="utf-8") if args.diff else ""
        verify = Path(args.verify).read_text(encoding="utf-8") if args.verify and Path(args.verify).exists() else None
        who = Path(args.herald).read_text(encoding="utf-8") if args.herald and Path(args.herald).exists() else None
    except (requests.RequestException, OSError, ValueError, KeyError) as exc:
        print(f"floor: {exc}", file=sys.stderr)
        return 2
    body = {"tag_name": plan["tag"], "ref": args.sha, "name": plan["tag"],
            "description": release.notes(plan, diff, verify, who), "assets": {"links": links}}
    if args.out:
        _write_json(Path(args.out), body)
    print(f"release {plan['tag']} from {args.sha[:8]}: the fix {plan['mr']} of pipeline {plan['pipeline']}")
    if args.dry_run:
        return 0
    token = os.environ.get("CI_JOB_TOKEN")
    if not token:
        print("floor: no CI_JOB_TOKEN: floor release creates releases only in CI (or use --dry-run)", file=sys.stderr)
        return 2
    try:
        resp = session.post(project + "/releases", json=body, headers={"JOB-TOKEN": token}, timeout=60)
    except requests.RequestException as exc:
        print(f"floor: {exc}", file=sys.stderr)
        return 2
    if resp.status_code >= 300:
        print(f"floor: the Releases API answered {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        return 1
    print(f"released: {resp.json().get('_links', {}).get('self', plan['tag'])}")
    return 0


def _cmd_herald(args: argparse.Namespace) -> int:
    try:
        text = herald.who(_read_json(args.manifest))
    except (OSError, ValueError) as exc:
        print(f"floor: {exc}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


def _memory_inputs(paths: list[str] | None) -> tuple[dict | None, dict | None, dict | None]:
    """Joins `floor memory --out` files (one per model) or plain {"model": MB} files. Gives the smallest
    passing limit, the peak RSS and the download size per model (a plain file has only the limit)."""
    limits, peaks, downloads = {}, {}, {}
    for path in paths or []:
        doc = _read_json(path)
        if "runs" in doc:
            limits[doc["model"]] = doc["smallest_passing_mb"]
            peaks[doc["model"]] = doc.get("peak_rss_mb")
            if doc.get("download_mb") is not None:
                downloads[doc["model"]] = doc["download_mb"]
        else:
            limits.update(doc)
    return limits or None, peaks or None, downloads or None


def _probe_inputs(paths: list[str] | None) -> dict | None:
    """Joins `floor probe --out` files, for example one per CPU model from parallel CI jobs."""
    runs = [run for path in paths or [] for run in _read_json(path)["runs"]]
    return {"runs": runs} if paths else None


def _command(args: argparse.Namespace) -> list[str] | None:
    cmd = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    if not cmd:
        print("floor: give the command after --", file=sys.stderr)
    return cmd or None


def _cmd_memory(args: argparse.Namespace) -> int:
    cmd = _command(args)
    if not cmd:
        return 2
    limits = [int(x) for x in args.limits.split(",")]
    # F8.1: what a user must download to run this model. Measured first, so a wrong path stops the job early.
    downloads = {"download_mb": offline.download_mb(args.artifact),
                 "download_bytes": offline.download_bytes(args.artifact)} if args.artifact else {}
    try:
        result = {"model": args.model, **memory.measure(cmd, limits, args.expect, args.timeout, sudo=not args.no_sudo,
                                                        cgroup_root=memory.CGROUP_ROOT if args.cgroup else None),
                  **downloads}
    except OSError as exc:  # --cgroup: not cgroup v2, not root, or no swap accounting
        print(f"floor: cannot set the memory limits in {memory.CGROUP_ROOT}: {exc}", file=sys.stderr)
        return 2
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", **result})
    rows = [("LIMIT_MB", "RESULT", "EXIT", "PEAK_RSS_MB")]
    rows += [(str(r["limit_mb"]), r["result"], str(r["exit"]), str(r["peak_rss_mb"])) for r in result["runs"]]
    _print_rows(rows)
    print(f"{args.model}: smallest passing limit {result['smallest_passing_mb']} MB, peak RSS {result['peak_rss_mb']} MB"
          + (f", download {result['download_mb']} MB" if downloads else ""))
    return 0


def _cmd_offline(args: argparse.Namespace) -> int:
    cmd = _command(args)
    if not cmd:
        return 2
    result = offline.check(cmd, args.expect, args.artifact, args.timeout, sudo=not args.no_sudo)
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", **result})
    print(f"result {result['result']}, network attempts {result['network_attempts']}, "
          f"offline {'proven' if result['offline'] else 'NOT proven'}, download {result['download_mb']} MB")
    for line in result["attempts"]:
        print(f"  {line}")
    return 0


def _cmd_audio(args: argparse.Namespace) -> int:
    try:
        seconds = energy.repeat_wav(args.src, args.out, args.copies, args.gap)
    except (ValueError, EOFError, OSError, wave.Error) as exc:
        print(f"floor: {exc}", file=sys.stderr)
        return 2
    print(f"{args.out}: {seconds:.1f} s ({seconds / 60:.3f} audio-minutes), {args.copies} copies, {args.gap} s gaps")
    return 0


def _cmd_energy(args: argparse.Namespace) -> int:
    builds = {}
    for item in args.build:
        name, _, exe = item.partition("=")
        if not name or not exe or not Path(exe).is_file() or name in builds:
            print(f"floor: --build needs NAME=EXE, an existing file and a new name, not {item!r}", file=sys.stderr)
            return 2
        builds[name] = str(Path(exe).absolute())
    if args.runs < 1 or args.warmup < 0:
        print("floor: --runs must be 1 or more and --warmup 0 or more", file=sys.stderr)
        return 2
    stray = energy.cwd_backends()
    if stray:
        print(f"floor: ggml also loads backends from the working directory, and it has {', '.join(stray)}. "
              "Run from another folder.", file=sys.stderr)
        return 2
    extra = args.cmd[1:] if args.cmd[:1] == ["--"] else args.cmd
    doc = energy.measure(builds, extra, str(Path(args.audio).absolute()), args.expect, args.runs, args.warmup,
                         args.timeout)
    if args.evidence:
        doc["evidence"] = args.evidence
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", **doc})
    rows = [("BUILD", "WALL_S", "CPU_S", "PEAK_RSS_MB", "VARIANT", "RESULT")]
    rows += [(name, str(b.get("wall_s", "-")), str(b.get("cpu_s", "-")), str(b.get("peak_rss_mb", "-")),
              b.get("loaded_variant") or "-", "pass" if "wall_s" in b else "FAIL") for name, b in doc["builds"].items()]
    _print_rows(rows)
    print(f"{doc['audio_minutes']} audio-minutes, median of {args.runs} runs per build, {doc['vcpus']} vCPUs, "
          f"{doc['cpu_model']}")
    return 0 if all("wall_s" in b for b in doc["builds"].values()) else 1


def _cmd_meter(args: argparse.Namespace) -> int:
    if args.action == "join":
        try:
            if not args.files:
                raise ValueError("give the floor meter stop --out files, one per job")
            result = meter.join({Path(path).stem: _read_json(path) for path in args.files})
        except (OSError, ValueError, KeyError) as exc:
            print(f"floor: {exc}", file=sys.stderr)
            return 2
        if args.evidence:
            result["evidence"] = args.evidence
        if args.out:
            _write_json(Path(args.out), {"tool": f"floor {__version__}", **result})
        _print_rows([("JOB", "WALL_S", "CPU_S", "MEMORY_GB_S")] + [
            (name, str(job["wall_s"]), str(job["cpu_s"]), str(job["memory_gb_s"])) for name, job in result["jobs"].items()])
        print(f"{len(result['jobs'])} jobs: wall {result['wall_s']} s, busy CPU {result['cpu_s']} s of "
              f"{result['vcpu_s']} vCPU-s, memory {result['memory_gb_s']} GB-s")
        return 0
    if not args.state:
        print("floor: floor meter start, sample and stop need --state", file=sys.stderr)
        return 2
    state = Path(args.state)
    if args.action == "sample":
        meter.sample(state, args.interval, cgroup=args.cgroup)
        return 0
    if not Path(meter.PROC_STAT).exists():
        print("floor: floor meter needs Linux (/proc/stat)", file=sys.stderr)
        return 2
    if args.action == "start":
        if args.cgroup and not Path(args.cgroup, "cpu.stat").exists():
            print(f"floor: not a cgroup v2 folder (no cpu.stat): {args.cgroup}", file=sys.stderr)
            return 2
        try:
            doc = meter.start(state, args.interval, args.cgroup)
        except (RuntimeError, OSError, ValueError) as exc:
            print(f"floor: {exc}", file=sys.stderr)
            return 2
        print(f"meter started: sampler PID {doc['pid']}, every {args.interval} s, {doc['vcpus']} vCPUs, "
              f"{doc['cpu_model']}, {'cgroup ' + doc['cgroup'] if doc['cgroup'] else 'whole machine'}")
        return 0
    if not state.exists():
        print(f"floor: no meter state file: {state} (run floor meter start first)", file=sys.stderr)
        return 2
    result = meter.stop(state)
    if args.evidence:
        result["evidence"] = args.evidence
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", **result})
    print(f"wall {result['wall_s']} s, busy CPU {result['cpu_s']} s of {result['vcpu_s']} vCPU-s, "
          f"memory {result['memory_gb_s']} GB-s (peak {result['memory_peak_gb']} GB), {result['samples']} samples")
    return 0

def _cmd_judge(args: argparse.Namespace) -> int:
    try:
        doc = policy.for_artifact(policy.load(args.policy), args.artifact)
    except (OSError, policy.PolicyError) as exc:
        print(f"floor: policy not valid: {exc}", file=sys.stderr)
        return 2
    scan = _read_json(args.scan)
    previous = _read_json(args.previous)
    limits, peaks, downloads = _memory_inputs(args.memory)
    result = judge.judge(doc, scan=scan["summary"] if scan else None, probe=_probe_inputs(args.probe),
                         memory=limits, peak_rss=peaks, model_download_mb=downloads,
                         connectivity=_read_json(args.connectivity), previous=_previous_floors(previous),
                         notices=args.notice)
    result["artifact"] = args.artifact
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", **result})
    rows = [("FLOOR", "STATUS", "VALUE", "PROOF", "POLICY")]
    for name, floor in result["floors"].items():
        value = floor.get("x86_64") or floor.get("offline") or json.dumps(floor.get("smallest_passing_mb"))
        proof = (floor.get("proof") or "-") + (" (coverage-limited)" if floor.get("coverage_limited") else "")
        rows.append((name, floor["status"], str(value), proof, {True: "met", False: "NOT met", None: "-"}[floor["meets_policy"]]))
    _print_rows(rows)
    for name, floor in result["floors"].items():
        for note in floor.get("notes") or []:
            print(f"{name}: {note}")
    for name in result["unmeasured"]:
        print(f"{name}: not measured")
    print(f"Pareto: {result['pareto']}. Decision: {result['decision']}.")
    for reason in result["reasons"]:
        print(f"  {reason}")
    return 0 if result["decision"] != "fail" else 1


def _print_table(reports: list[FileReport], summary: dict) -> None:
    rows = [("FILE", "ROLE", "LEVEL", "EXTRAS")]
    for r in reports:
        role = f"variant:{r.variant}" if r.role == "variant" else r.role
        level = "error" if r.error else level_name(r.level)
        rows.append((r.path, role, level, ",".join(r.extras) or "-"))
    _print_rows(rows)
    floor = summary["floor"]
    extras = f" + {', '.join(floor['extras'])}" if floor["extras"] else ""
    print()
    print(f"Floor: {floor['level']}{extras}")
    if floor["sources"]:
        print(f"  set by: {', '.join(floor['sources'])}")
    print(f"Highest level found anywhere: {summary['highest_level_found']}")
    if summary["files"]["errors"]:
        print(f"Files with errors: {', '.join(summary['files']['errors'])}")


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):  # a console that cannot show →, Δ or ₂ gets "?", not a crash
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(prog="floor", description="Proves, for every release, who can still use it.")
    parser.add_argument("--version", action="version", version=f"floor {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="static CPU-floor scan of ELF files (PRD F2)")
    scan.add_argument("paths", nargs="+", help="files or directories to scan")
    scan.add_argument("--json", metavar="FILE", help="write the full report as JSON")
    scan.add_argument("--role", choices=ROLES, help="use one role for every file (for example distro)")
    scan.add_argument("--quiet", action="store_true", help="do not print the table")
    scan.set_defaults(func=_cmd_scan)

    image = sub.add_parser("image", help="pull the /app layer of published images and scan it (PRD F10.1)")
    image.add_argument("refs", nargs="+", help="tags or digests, for example main-a1867e0")
    image.add_argument("--repo", default=DEFAULT_REPO, help=f"repository on ghcr.io (default {DEFAULT_REPO})")
    image.add_argument("--out", metavar="DIR", help="write one JSON report per image into DIR")
    image.add_argument("--verbose", action="store_true", help="print the file table of each image")
    image.set_defaults(func=_cmd_image)

    sample = sub.add_parser("sample", help="choose main-<sha> images for the backtest (PRD F10.1)")
    sample.add_argument("--repo", default=DEFAULT_REPO, help=f"repository on ghcr.io (default {DEFAULT_REPO})")
    sample.add_argument("--prefix", default=backtest.DEFAULT_PREFIX,
                        help=f"tag prefix before the commit hash (default {backtest.DEFAULT_PREFIX}; or main-cuda-)")
    sample.add_argument("--count", type=int, default=30, help="images spread evenly in time (default 30)")
    sample.add_argument("--around", action="append", metavar="DATE[:LABEL]",
                        help="also take every image near this date (repeat; default: #3510 and #3814)")
    sample.add_argument("--window-days", type=int, default=14, help="days on each side of --around (default 14)")
    sample.add_argument("--batch", type=int, default=10, help="refs per output line (default 10)")
    sample.add_argument("--out", metavar="FILE", help="write the choice as JSON")
    sample.set_defaults(func=_cmd_sample)

    tl = sub.add_parser("timeline", help="join floor image reports into one timeline (PRD F10.1)")
    tl.add_argument("paths", nargs="+", help="report files or directories")
    tl.add_argument("--out", metavar="FILE", help="write the timeline as JSON")
    tl.set_defaults(func=_cmd_timeline)

    bf = sub.add_parser("backtest-footprint", help="downloads and runner time of the backtest (PRD F14.4)")
    bf.add_argument("timelines", nargs="+", metavar="TIMELINE", help="floor timeline --out files")
    bf.add_argument("--runs", nargs="+", required=True, metavar="FILE",
                    help="gh run view <id> --json databaseId,jobs output, one file per sweep run")
    bf.add_argument("--repo", default=DEFAULT_REPO, help="image repository")
    bf.add_argument("--out", metavar="FILE", help="write the result as JSON")
    bf.set_defaults(func=_cmd_backtest_footprint)

    sc = sub.add_parser("spotcheck", help="true-positive rate of the keyword counts from a labelled sample (PRD §3.2)")
    sc.add_argument("labels", help="the spot-check file: the search hits, the seed and one label per sampled hit")
    sc.set_defaults(func=_cmd_spotcheck)

    hyp = sub.add_parser("h1", help="H-1 analysis: flips in a timeline vs changes in the floor paths (PRD F10.3)")
    hyp.add_argument("timeline", help="timeline JSON from floor timeline")
    hyp.add_argument("--git", metavar="DIR", help="a whisper.cpp clone (--filter=blob:none is enough)")
    hyp.add_argument("--pair", metavar="TIMELINE", help="a second timeline (for example main-cuda-) to join on the commit")
    hyp.add_argument("--out", metavar="FILE", help="write the analysis as JSON")
    hyp.set_defaults(func=_cmd_h1)

    pr = sub.add_parser("probe", help="run a command under QEMU on old CPU models, with controls (PRD F3)")
    pr.add_argument("--cpu", action="append", choices=list(qemu.CPU_MODELS), help="CPU model (repeat; default: all)")
    pr.add_argument("--expect", help="text that the output must contain (the reference transcript)")
    pr.add_argument("--sysroot", help="root of an extracted image filesystem (qemu -L)")
    pr.add_argument("--env", action="append", metavar="KEY=VALUE", help="environment for the command (repeat)")
    pr.add_argument("--timeout", type=float, default=900, help="seconds per run (default 900)")
    pr.add_argument("--label", help="a name for this build, written to the JSON")
    pr.add_argument("--out", metavar="FILE", help="write the result as JSON")
    pr.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command and arguments")
    pr.set_defaults(func=_cmd_probe)

    pol = sub.add_parser("policy", help="validate .floor/policy.yml against its JSON Schema (PRD F1.1)")
    pol.add_argument("file", nargs="?", default=str(policy.DEFAULT_POLICY), help="policy file (default: .floor/policy.yml)")
    pol.add_argument("--schema", default=str(policy.DEFAULT_SCHEMA), help="JSON Schema file")
    pol.add_argument("--artifact", help="print the resolved policy for this artifact")
    pol.set_defaults(func=_cmd_policy)

    jd = sub.add_parser("judge", help="mark each floor held, lowered, raised or inconclusive (PRD F5)")
    jd.add_argument("--policy", default=str(policy.DEFAULT_POLICY), help="policy file")
    jd.add_argument("--artifact", help="artifact name, for per-artifact floors")
    jd.add_argument("--scan", metavar="FILE", help="floor scan --json output")
    jd.add_argument("--probe", action="append", metavar="FILE", help="floor probe --out output (repeat per CPU model)")
    jd.add_argument("--memory", action="append", metavar="FILE", help="floor memory --out output (repeat per model)")
    jd.add_argument("--connectivity", metavar="FILE",
                    help='floor offline --out output, or JSON {"offline": bool, "network_attempts": int}')
    jd.add_argument("--previous", metavar="FILE", help="manifest (or judge output) of the previous release")
    jd.add_argument("--notice", action="append", metavar="FLOOR", help="a floor with a merged Leave-Behind Notice (repeat)")
    jd.add_argument("--out", metavar="FILE", help="write the result as JSON")
    jd.set_defaults(func=_cmd_judge)

    rt = sub.add_parser("ratchet", help="a looser policy needs a merged Leave-Behind Notice (PRD F1.2)")
    rt.add_argument("new", nargs="?", default=str(policy.DEFAULT_POLICY), help="the changed policy file")
    rt.add_argument("--base", metavar="REF", help="target branch: read the old policy and the notices from git")
    rt.add_argument("--old", metavar="FILE", help="old policy file (without git)")
    rt.add_argument("--notices", default=ratchet.NOTICE_DIR, metavar="DIR", help="merged notices, with --old")
    rt.add_argument("--approvals", metavar="URL", help="GitLab API URL of the project (.../projects/ID): a notice "
                    "counts only when a human code owner approved its merged MR (F6.1)")
    rt.add_argument("--default-branch", metavar="BRANCH", help="the branch that notice MRs merge into, with --approvals")
    rt.add_argument("--humans", metavar="NAMES", help="human usernames, space-separated (default: $FLOOR_HUMANS)")
    rt.set_defaults(func=_cmd_ratchet)

    nt = sub.add_parser("notice", help="check that Leave-Behind Notices are complete (PRD F6, §11.2)")
    nt.add_argument("files", nargs="+", help="notice files")
    nt.add_argument("--draft", action="store_true", help="allow an empty 'Approved by' (open notice MR)")
    nt.set_defaults(func=_cmd_notice)

    nd = sub.add_parser("notice-draft", help="draft a Leave-Behind Notice when the fix and the fallback "
                        "did not hold a floor (PRD F4.5)")
    nd.add_argument("--judge", required=True, metavar="FILE", help="floor judge output for the branch")
    nd.add_argument("--policy", default=str(policy.DEFAULT_POLICY), help="policy file")
    nd.add_argument("--root", default=".", help="repository root (is the canned config on the branch?)")
    nd.add_argument("--diagnosis", metavar="FILE", help="the MR description, where the agent states the cause (F4.2)")
    nd.add_argument("--truncated", action="store_true", help="GitLab cut the MR description short")
    nd.add_argument("--mr", metavar="URL", help="the MR with the fix")
    nd.add_argument("--evidence", metavar="URL", help="the gate pipeline or job")
    nd.add_argument("--scenarios", default=".floor/scenarios", metavar="DIR", help="ΔM scenarios (by dimension)")
    nd.add_argument("--notices", default=ratchet.NOTICE_DIR, metavar="DIR", help="merged notices (for the number)")
    nd.add_argument("--out", default="out/notice", metavar="DIR", help="folder for the draft")
    nd.set_defaults(func=_cmd_notice_draft)

    mem = sub.add_parser("memory", help="smallest cgroup memory limit that passes, and peak RSS (PRD F7; Linux)")
    mem.add_argument("--model", required=True, help="model name, for example tiny")
    mem.add_argument("--limits", default=",".join(map(str, memory.DEFAULT_LIMITS_MB)), help="MB, comma-separated")
    mem.add_argument("--expect", help="text that the output must contain")
    mem.add_argument("--timeout", type=float, default=900, help="seconds per run")
    mem.add_argument("--no-sudo", action="store_true", help="do not prefix sudo (already root)")
    mem.add_argument("--cgroup", action="store_true",
                     help="no systemd: one child cgroup of /sys/fs/cgroup per run (cgroup v2, as root)")
    mem.add_argument("--artifact", action="append", metavar="FILE",
                     help="file a user must download for this run, for example the model (repeat; F8.1)")
    mem.add_argument("--out", metavar="FILE", help="write the result as JSON")
    mem.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command and arguments")
    mem.set_defaults(func=_cmd_memory)

    off = sub.add_parser("offline", help="run with no network under strace; count network attempts (PRD F8; Linux)")
    off.add_argument("--expect", help="text that the output must contain")
    off.add_argument("--artifact", action="append", metavar="FILE", help="file a user must download (repeat)")
    off.add_argument("--timeout", type=float, default=900, help="seconds")
    off.add_argument("--no-sudo", action="store_true", help="do not prefix sudo (already root)")
    off.add_argument("--out", metavar="FILE", help="write the result as JSON")
    off.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command and arguments")
    off.set_defaults(func=_cmd_offline)

    au = sub.add_parser("audio", help="repeat a WAV file with silence between the copies: the energy test audio "
                                      "(PRD F14.2)")
    au.add_argument("src", help="WAV file, for example samples/jfk.wav")
    au.add_argument("out", help="output WAV file")
    au.add_argument("--copies", type=int, default=11, help="number of copies")
    au.add_argument("--gap", type=float, default=1.0, help="seconds of silence between the copies")
    au.set_defaults(func=_cmd_audio)

    en = sub.add_parser("energy", help="time each build on the same audio with GNU time: the medians of the runs "
                                       "(PRD F14.2; Linux)")
    en.add_argument("--build", action="append", required=True, metavar="NAME=EXE",
                    help="a build and its whisper-cli (repeat). Each run is EXE ARGS -f AUDIO")
    en.add_argument("--audio", required=True, help="WAV file, for example the floor audio output")
    en.add_argument("--expect", help="text that each transcript must contain")
    en.add_argument("--runs", type=int, default=5, help="counted runs per build")
    en.add_argument("--warmup", type=int, default=1, help="rounds before the counted runs")
    en.add_argument("--timeout", type=float, default=900, help="seconds per run")
    en.add_argument("--evidence", metavar="URL", help="the CI run that measured it")
    en.add_argument("--out", metavar="FILE", help="write the result as JSON (footprint --energy reads it)")
    en.add_argument("cmd", nargs=argparse.REMAINDER, help="-- the arguments of each build, for example -m MODEL -t 4")
    en.set_defaults(func=_cmd_energy)

    mt = sub.add_parser("meter", help="CPU and memory use of one release check (PRD F14.1 R2; Linux)")
    mt.add_argument("action", choices=["start", "sample", "stop", "join"],
                    help="start: write the state file and start the sampler; sample: the sampler itself; "
                         "stop: stop the sampler and give the totals; join: add the totals of the jobs of one "
                         "release check")
    mt.add_argument("files", nargs="*", help="floor meter stop --out files, one per job (join)")
    mt.add_argument("--state", metavar="FILE", help="state file of this meter (start, sample, stop)")
    mt.add_argument("--cgroup", nargs="?", const=meter.CGROUP, metavar="DIR",
                    help=f"count one cgroup v2 group, not the whole machine (start; default {meter.CGROUP})")
    mt.add_argument("--interval", type=float, default=5.0, help="seconds between memory samples")
    mt.add_argument("--evidence", metavar="URL", help="the CI job or pipeline that measured it (stop, join)")
    mt.add_argument("--out", metavar="FILE", help="write the totals as JSON (stop, join)")
    mt.set_defaults(func=_cmd_meter)

    pa = sub.add_parser("paths", help="path allowlist for agent MRs and merge-bot merges (PRD F4.2, §10.1)")
    pa.add_argument("--actor", required=True, choices=["agent", "merge-bot", "auto"],
                    help="who will change or merge; auto: an agent unless the pipeline user and the MR author "
                         "are in FLOOR_HUMANS (CI variables)")
    pa.add_argument("--base", default="origin/main", metavar="REF", help="target branch (default origin/main)")
    pa.add_argument("files", nargs="*", help="changed paths (default: git diff BASE...HEAD)")
    pa.set_defaults(func=_cmd_paths)

    fb = sub.add_parser("fallback", help="apply the canned inclusive config to the build files (PRD F4.3)")
    fb.add_argument("--root", default=".", help="repository root")
    fb.add_argument("--dockerfile", action="append", help="Dockerfile path relative to root (default: .devops/*.Dockerfile)")
    fb.add_argument("--artifact", default="main", help="override file name in .floor/overrides/")
    fb.add_argument("--judge", metavar="FILE", help="floor judge output: act only when the gate failed")
    fb.add_argument("--policy", default=str(policy.DEFAULT_POLICY), help="policy file (repair.fallback)")
    fb.add_argument("--patch", metavar="FILE", help="write the changes as a patch for git apply; change no file")
    fb.set_defaults(func=_cmd_fallback)

    pg = sub.add_parser("page", help="build the Floor page from the evidence files (PRD F12.2)")
    pg.add_argument("--evidence", default=".floor/evidence", help="evidence folder")
    pg.add_argument("--notices", default=".floor/notices", help="notices folder")
    pg.add_argument("--out", default="site", help="output folder (index.html)")
    pg.set_defaults(func=_cmd_page)

    dm = sub.add_parser("delta-m", help="ΔM scenario: range and sensitivity table (PRD F14.3, §13.3)")
    dm.add_argument("scenario", help="scenario YAML (see .floor/scenarios/TEMPLATE.yml)")
    dm.add_argument("--judge", metavar="FILE", help="floor judge output: ΔM is 0 when every floor holds")
    dm.add_argument("--out", metavar="FILE", help="write the result as JSON")
    dm.set_defaults(func=_cmd_delta_m)

    mf = sub.add_parser("manifest", help="write floor-manifest.json (in-toto Statement) and the diff (PRD F5.3)")
    mf.add_argument("--judge", required=True, metavar="FILE", help="floor judge --out output")
    mf.add_argument("--subject", required=True, help="image name, for example registry.gitlab.com/g/whisper.cpp/server")
    mf.add_argument("--digest", required=True, help="image digest (sha256:...)")
    mf.add_argument("--release", required=True, help="release tag, for example v1.8.1-floor.1")
    mf.add_argument("--commit", required=True, help="source commit")
    mf.add_argument("--scan", metavar="FILE", help="floor scan --json output")
    mf.add_argument("--cmake-flags", help="the CMake flags of the build")
    mf.add_argument("--base-image", help="base image digest")
    mf.add_argument("--build-cpu", help="CPU model of the machine that ran the build (H-1: it can set the floor)")
    mf.add_argument("--previous", metavar="FILE", help="floor-manifest.json of the previous release")
    mf.add_argument("--evidence", metavar="URL", help="job URL to record as evidence")
    mf.add_argument("--floor-evidence", action="append", metavar="FLOOR=URL",
                    help="the job that measured one floor, for example memory=<job URL> (repeat; default --evidence)")
    mf.add_argument("--fixed-by", choices=["agent", "fallback"], help="what lowered a floor in this release")
    mf.add_argument("--notice", action="append", metavar="REF", help="a merged Leave-Behind Notice (repeat)")
    mf.add_argument("--project-url", help="project URL for predicateType (default: $CI_PROJECT_URL)")
    mf.add_argument("--out", default="floor-manifest.json", metavar="FILE", help="output (default floor-manifest.json)")
    mf.add_argument("--diff", metavar="FILE", help="also write the diff as Markdown")
    mf.add_argument("--delta-m", metavar="FILE", help="floor delta-m --out output (used when a floor rises)")
    mf.add_argument("--footprint", metavar="FILE", help="floor footprint check --out output (the SCI values)")
    mf.set_defaults(func=_cmd_manifest)

    fp = sub.add_parser("footprint", help="SCI with Impact Framework manifests (PRD F14.1)")
    fp.add_argument("action", choices=["write", "stale", "check"],
                    help="write: make the manifests from the evidence; stale: fail when the manifests in --out-dir "
                         "differ from the evidence; check: recompute every if-run output")
    fp.add_argument("files", nargs="*", help="if-run output files (check)")
    fp.add_argument("--config", default=str(footprint.DEFAULT_CONFIG), help="coefficients and sites")
    fp.add_argument("--energy", default=str(footprint.ENERGY_FILE), metavar="FILE", help="floor energy --out output")
    fp.add_argument("--meter", default=str(footprint.METER_FILE), metavar="FILE", help="floor meter stop --out output")
    fp.add_argument("--out-dir", default=str(footprint.IMPACT_DIR), metavar="DIR", help="manifest folder (write, stale)")
    fp.add_argument("--out", metavar="FILE", help="write the SCI summary as JSON (check)")
    fp.add_argument("--expect", metavar="FILE", help="a committed SCI summary: fail when the results differ (check)")
    fp.set_defaults(func=_cmd_footprint)

    df = sub.add_parser("diff", help="readable diff of two floor manifests (AC-F5)")
    df.add_argument("old", help="previous floor-manifest.json")
    df.add_argument("new", help="new floor-manifest.json")
    df.set_defaults(func=_cmd_diff)

    at = sub.add_parser("attest", help="inputs and check of the signed floor manifest (PRD F5.4; cosign signs)")
    at.add_argument("action", choices=["predicate", "identity", "check"],
                    help="predicate: write the predicate for cosign attest and print its type; identity: print the "
                         "certificate identity of this CI job; check: compare cosign verify-attestation output "
                         "with the manifest")
    at.add_argument("--manifest", metavar="FILE", help="floor-manifest.json (predicate, check)")
    at.add_argument("--out", metavar="FILE", help="where to write the predicate (predicate)")
    at.add_argument("--verified", metavar="FILE", help="the output of cosign verify-attestation (check)")
    at.add_argument("--token-env", default="SIGSTORE_ID_TOKEN", metavar="NAME",
                    help="the variable with the GitLab ID token (identity; default SIGSTORE_ID_TOKEN)")
    at.set_defaults(func=_cmd_attest)

    rl = sub.add_parser("release", help="cut <tag>-floor.N after a fix MR of a tag pipeline merged (PRD F4.4)")
    rl.add_argument("--sha", required=True, help="the commit of this default-branch pipeline")
    rl.add_argument("--default-branch", required=True, help="the default branch, for example main")
    rl.add_argument("--api", required=True, metavar="URL", help="GitLab API URL ($CI_API_V4_URL)")
    rl.add_argument("--project", required=True, help="project id ($CI_PROJECT_ID)")
    rl.add_argument("--diff", metavar="FILE", help="the floor diff of the manifest (floor manifest --diff)")
    rl.add_argument("--verify", metavar="FILE", help="the verify command of the attest job")
    rl.add_argument("--herald", metavar="FILE", help="the \"Who this release serves\" section (floor herald --out)")
    rl.add_argument("--link", action="append", metavar="NAME=URL", help="a release asset link (repeat)")
    rl.add_argument("--out", metavar="FILE", help="also write the release request as JSON")
    rl.add_argument("--dry-run", action="store_true", help="decide and print, but create no release")
    rl.set_defaults(func=_cmd_release)

    hd = sub.add_parser("herald", help="\"Who this release serves\" from the floor manifest (PRD F12.1, template)")
    hd.add_argument("--manifest", required=True, metavar="FILE", help="floor-manifest.json")
    hd.add_argument("--out", metavar="FILE", help="also write the section to this Markdown file")
    hd.set_defaults(func=_cmd_herald)

    args = parser.parse_args(argv)
    return args.func(args)
