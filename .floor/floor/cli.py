"""Command line: python -m floor <command>."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests

from . import __version__
from . import backtest, h1, judge, manifest, policy, qemu
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


def _read_json(path: str | None) -> dict | None:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else None


def _previous_floors(doc: dict | None) -> dict | None:
    """Accepts a manifest (floors under "predicate") or a judge output."""
    if not doc:
        return None
    return (doc.get("predicate") or doc).get("floors")


def _cmd_manifest(args: argparse.Namespace) -> int:
    verdict = _read_json(args.judge)
    scan = _read_json(args.scan)
    previous = _read_json(args.previous)
    doc = manifest.build(verdict, subject=args.subject, digest=args.digest, release=args.release, commit=args.commit,
                         scan=scan["summary"] if scan else None, cmake_flags=args.cmake_flags,
                         base_image=args.base_image, previous=previous, evidence=args.evidence,
                         fixed_by=args.fixed_by, notices=args.notice, project_url=args.project_url)
    _write_json(Path(args.out), doc)
    text = manifest.diff_markdown(previous, doc)
    if args.diff:
        Path(args.diff).write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


def _cmd_diff(args: argparse.Namespace) -> int:
    print(manifest.diff_markdown(_read_json(args.old), _read_json(args.new)), end="")
    return 0


def _cmd_judge(args: argparse.Namespace) -> int:
    try:
        doc = policy.for_artifact(policy.load(args.policy), args.artifact)
    except (OSError, policy.PolicyError) as exc:
        print(f"floor: policy not valid: {exc}", file=sys.stderr)
        return 2
    scan = _read_json(args.scan)
    previous = _read_json(args.previous)
    result = judge.judge(doc, scan=scan["summary"] if scan else None, probe=_read_json(args.probe),
                         memory=_read_json(args.memory), connectivity=_read_json(args.connectivity),
                         previous=_previous_floors(previous), notices=args.notice)
    result["artifact"] = args.artifact
    if args.out:
        _write_json(Path(args.out), {"tool": f"floor {__version__}", **result})
    rows = [("FLOOR", "STATUS", "VALUE", "PROOF", "POLICY")]
    for name, floor in result["floors"].items():
        value = floor.get("x86_64") or floor.get("offline") or json.dumps(floor.get("smallest_passing_mb"))
        proof = (floor.get("proof") or "-") + (" (coverage-limited)" if floor.get("coverage_limited") else "")
        rows.append((name, floor["status"], str(value), proof, {True: "met", False: "NOT met", None: "-"}[floor["meets_policy"]]))
    _print_rows(rows)
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
    jd.add_argument("--probe", metavar="FILE", help="floor probe --out output")
    jd.add_argument("--memory", metavar="FILE", help='JSON {"tiny": MB, ...}: smallest passing memory limits')
    jd.add_argument("--connectivity", metavar="FILE", help='JSON {"offline": bool, "network_attempts": int}')
    jd.add_argument("--previous", metavar="FILE", help="manifest (or judge output) of the previous release")
    jd.add_argument("--notice", action="append", metavar="FLOOR", help="a floor with a merged Leave-Behind Notice (repeat)")
    jd.add_argument("--out", metavar="FILE", help="write the result as JSON")
    jd.set_defaults(func=_cmd_judge)

    mf = sub.add_parser("manifest", help="write floor-manifest.json (in-toto Statement) and the diff (PRD F5.3)")
    mf.add_argument("--judge", required=True, metavar="FILE", help="floor judge --out output")
    mf.add_argument("--subject", required=True, help="image name, for example registry.gitlab.com/g/whisper.cpp/server")
    mf.add_argument("--digest", required=True, help="image digest (sha256:...)")
    mf.add_argument("--release", required=True, help="release tag, for example v1.8.1-floor.1")
    mf.add_argument("--commit", required=True, help="source commit")
    mf.add_argument("--scan", metavar="FILE", help="floor scan --json output")
    mf.add_argument("--cmake-flags", help="the CMake flags of the build")
    mf.add_argument("--base-image", help="base image digest")
    mf.add_argument("--previous", metavar="FILE", help="floor-manifest.json of the previous release")
    mf.add_argument("--evidence", metavar="URL", help="job URL to record as evidence")
    mf.add_argument("--fixed-by", choices=["agent", "fallback"], help="what lowered a floor in this release")
    mf.add_argument("--notice", action="append", metavar="REF", help="a merged Leave-Behind Notice (repeat)")
    mf.add_argument("--project-url", help="project URL for predicateType (default: $CI_PROJECT_URL)")
    mf.add_argument("--out", default="floor-manifest.json", metavar="FILE", help="output (default floor-manifest.json)")
    mf.add_argument("--diff", metavar="FILE", help="also write the diff as Markdown")
    mf.set_defaults(func=_cmd_manifest)

    df = sub.add_parser("diff", help="readable diff of two floor manifests (AC-F5)")
    df.add_argument("old", help="previous floor-manifest.json")
    df.add_argument("new", help="new floor-manifest.json")
    df.set_defaults(func=_cmd_diff)

    args = parser.parse_args(argv)
    return args.func(args)
