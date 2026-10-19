"""The -floor.N release (PRD F4.4, AC-F4a, D-010, D-024): what the default-branch pipeline cuts after a fix merged.

A person pushes an upstream tag. Its pipeline fails at the judge, and the floor-repair flow opens a fix MR
from `floor-fix/<pipeline id>` into the default branch (D-021). GitLab merges it when the gate passes (T-05).
The pipeline of the merged commit passes the judge and signs the manifest (`attest`, D-023). Then this
module cuts `<tag>-floor.N` from that commit, through the Releases API with the job token (GitLab makes
the tag from `ref`).

The decision is a script's: the commit must be the merge of a fix MR, and the pipeline that the fix
repaired must be a tag pipeline. Any other commit gets no release. A tag never moves: N only grows.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable

FIX_BRANCH = re.compile(r"^floor-fix/(\d+)$")
FLOOR_TAG = re.compile(r"-floor\.\d+$")


def fix_pipeline(merge_requests: list[dict], default_branch: str) -> tuple[int, dict] | None:
    """The id of the failed pipeline that a merged fix MR of this commit repaired, and the MR."""
    for mr in merge_requests:
        match = FIX_BRANCH.match(mr.get("source_branch") or "")
        if match and mr.get("state") == "merged" and mr.get("target_branch") == default_branch:
            return int(match.group(1)), mr
    return None


def next_tag(base: str, tags: Iterable[str]) -> str:
    pattern = re.compile(re.escape(base) + r"-floor\.(\d+)$")
    found = [int(m.group(1)) for tag in tags if (m := pattern.match(tag))]
    return f"{base}-floor.{max(found, default=0) + 1}"


def plan(sha: str, default_branch: str, get: Callable[[str], object]) -> dict:
    """{"tag", "base", "pipeline", "mr"} for the release of this commit, or {"skip": reason}.

    `get` reads one GitLab API path of the project (for example "/repository/tags") and returns the JSON.
    """
    fix = fix_pipeline(get(f"/repository/commits/{sha}/merge_requests"), default_branch)
    if not fix:
        return {"skip": f"commit {sha[:8]} is not the merge of a floor-fix/ MR into {default_branch}"}
    pipeline_id, mr = fix
    pipeline = get(f"/pipelines/{pipeline_id}")
    base = pipeline.get("ref") or ""
    if not pipeline.get("tag"):
        return {"skip": f"{mr['web_url']} repaired pipeline {pipeline_id} of {base or '?'}, not a tag pipeline"}
    if FLOOR_TAG.search(base):
        return {"skip": f"pipeline {pipeline_id} is the pipeline of a -floor tag ({base})"}
    tags = [t["name"] for t in get(f"/repository/tags?search=^{base}-floor.&per_page=100")]
    return {"tag": next_tag(base, tags), "base": base, "pipeline": pipeline_id, "mr": mr["web_url"]}


def notes(release: dict, diff: str, verify: str | None, herald: str | None = None) -> str:
    """The release description: Herald's section, the fix, the floor diff and the command that checks the signature."""
    lines = [f"Rieux release of `{release['base']}` with every floor held.", ""]
    if herald:
        lines += [herald.strip(), ""]
    lines += [f"- The gate failed on `{release['base']}` (pipeline {release['pipeline']}).",
              f"- The fix: {release['mr']}. The pipeline of the merged commit proved the floors again.", "",
              diff.strip(), ""]
    if verify:
        lines += ["Check the signed Floor Manifest (keyless, Sigstore):", "", "```", verify.strip(), "```", ""]
    return "\n".join(lines)
