"""Command line: python -m floor <command>."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests

from . import __version__
from . import backtest
from .isa.levels import level_name
from .isa.scan import ROLES, FileReport, scan_path, summarize
from .oci import DEFAULT_REPO, Registry, inspect_image, pull_layer


def _write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


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
    tags = backtest.main_tags(Registry(args.repo).tags())
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

    args = parser.parse_args(argv)
    return args.func(args)
