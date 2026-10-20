"""H-1 analysis (F10.3): does the build machine set the floor?

For every flip in a backtest timeline (two images next to each other in time with
different floors), the analysis lists the files that changed between the two commits
in the paths that can change the floor: the Dockerfiles, the image workflow and the
ggml CPU code and build files. A flip with no change in these paths can come only
from the build machine.
"""

from __future__ import annotations

import re
import subprocess

from .isa.levels import parse_level

# Paths in whisper.cpp that can change the CPU floor of a published image.
FLOOR_PATHS = (
    ".devops/",
    ".github/workflows/docker.yml",
    "CMakeLists.txt",
    "Makefile",
    "cmake/",
    "ggml/CMakeLists.txt",
    "ggml/cmake/",
    "ggml/src/CMakeLists.txt",
    "ggml/src/ggml-cpu/",
)
_SHA_RE = re.compile(r"([0-9a-f]{40})$")


def commit_of(ref: str) -> str | None:
    """Returns the commit hash in a `main-<sha>` style tag."""
    match = _SHA_RE.search(ref)
    return match.group(1) if match else None


def flips(rows: list[dict]) -> list[tuple[dict, dict]]:
    """Returns the pairs of images, next to each other in time, whose floors differ."""
    ordered = sorted(rows, key=lambda row: (row["created"] or "", row["ref"]))
    return [(a, b) for a, b in zip(ordered, ordered[1:]) if a["floor"] != b["floor"]]


def changed_paths(git_dir: str, old: str, new: str, paths: tuple[str, ...] = FLOOR_PATHS) -> list[str]:
    """Lists the files below ``paths`` that differ between two commits. Needs only trees,
    so a `--filter=blob:none` clone is enough."""
    out = subprocess.run(["git", "-C", git_dir, "diff", "--name-only", old, new, "--", *paths],
                         check=True, capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def same_commit_pairs(rows_a: list[dict], rows_b: list[dict]) -> list[dict]:
    """Joins two timelines (for example `main-` and `main-cuda-`) on the commit hash and
    returns the commits whose two images have different floors."""
    by_commit = {commit_of(row["ref"]): row for row in rows_b}
    pairs = []
    for row in rows_a:
        other = by_commit.get(commit_of(row["ref"]))
        if other is not None and other["floor"] != row["floor"]:
            pairs.append({"commit": commit_of(row["ref"]), "a": row["ref"], "a_floor": row["floor"],
                          "b": other["ref"], "b_floor": other["floor"]})
    return pairs


def shared_commits(rows_a: list[dict], rows_b: list[dict]) -> int:
    """Counts the commits that have an image in both timelines."""
    return len({commit_of(row["ref"]) for row in rows_a} & {commit_of(row["ref"]) for row in rows_b} - {None})


def pair_verdict(pairs: list[dict], shared: int) -> str:
    """The verdict from images of one commit built twice (for example by two image jobs)."""
    if not shared:
        return "no shared commits"
    if not pairs:
        return f"not supported: all {shared} shared commits have the same floor in both images"
    return (f"supported: {len(pairs)} of {shared} shared commits have different floors in the two images. "
            "The source is the same, so the build machine set the floor")


def analyse(rows: list[dict], git_dir: str | None) -> dict:
    """Returns the flips, the floor-relevant changes at each flip, and a verdict."""
    found = []
    for a, b in flips(rows):
        old, new = commit_of(a["ref"]), commit_of(b["ref"])
        changes = changed_paths(git_dir, old, new) if git_dir and old and new else None
        found.append({
            "from": {"ref": a["ref"], "created": a["created"], "floor": a["floor"]},
            "to": {"ref": b["ref"], "created": b["created"], "floor": b["floor"]},
            "direction": "raised" if parse_level(b["floor"]) > parse_level(a["floor"]) else "lowered",
            "floor_path_changes": changes,
        })
    checked = [f for f in found if f["floor_path_changes"] is not None]
    unexplained = [f for f in checked if not f["floor_path_changes"]]
    if not found:
        verdict = "no flips"
    elif not checked:
        verdict = "not checked (no git history)"
    elif len(unexplained) == len(checked):
        verdict = "supported: no flip has a change in the floor paths, so the build machine set the floor"
    elif unexplained:
        verdict = "partly supported: some flips have no change in the floor paths"
    else:
        verdict = "not supported: every flip has a change in the floor paths"
    levels = [row["floor"] for row in rows]
    return {
        "images": len(rows),
        "levels": {level: levels.count(level) for level in sorted(set(levels))},
        "flips": len(found),
        "flips_without_floor_path_changes": len(unexplained),
        "floor_paths": list(FLOOR_PATHS),
        "verdict": verdict,
        "details": found,
    }
