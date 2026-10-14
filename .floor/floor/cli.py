"""Command line: python -m floor <command>."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .isa.levels import level_name
from .isa.scan import ROLES, FileReport, scan_path, summarize


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
        doc = {"tool": f"floor {__version__}", "summary": summary, "files": [r.to_dict() for r in reports]}
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    if not args.quiet:
        _print_table(reports, summary)
    return 0


def _print_table(reports: list[FileReport], summary: dict) -> None:
    rows = [("FILE", "ROLE", "LEVEL", "EXTRAS")]
    for r in reports:
        role = f"variant:{r.variant}" if r.role == "variant" else r.role
        level = "error" if r.error else level_name(r.level)
        rows.append((r.path, role, level, ",".join(r.extras) or "-"))
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    for row in rows:
        print(f"{row[0]:<{widths[0]}}  {row[1]:<{widths[1]}}  {row[2]:<{widths[2]}}  {row[3]}")
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

    args = parser.parse_args(argv)
    return args.func(args)
