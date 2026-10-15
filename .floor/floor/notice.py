"""Leave-Behind Notice (PRD F6, §11.2): parse, check that it is complete, check who approved it."""

from __future__ import annotations

import re

FIELDS = ("Floor change", "Reason", "Tried first", "Who is affected", "ΔM (scenario)", "Guidance", "Approved by")
HEADING = "## Leave-Behind Notice"
_LINE = re.compile(r"^(" + "|".join(re.escape(f) for f in FIELDS) + r"):[ \t]*(.*?)[ \t]*$", re.MULTILINE)
_PLACEHOLDER = re.compile(r"<[^<>]+>")


def parse(text: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in _LINE.finditer(text)}


def problems(text: str, draft: bool = False) -> list[str]:
    """Empty list = complete. ``draft`` allows an empty approver (the notice MR is still open)."""
    found = []
    if HEADING not in text:
        found.append(f"no '{HEADING}' heading")
    fields = parse(text)
    for field in FIELDS:
        value = fields.get(field, "")
        if draft and field == "Approved by":
            continue
        if not value:
            found.append(f"{field}: missing")
        elif _PLACEHOLDER.search(value):
            found.append(f"{field}: still has a placeholder")
    return found


def approval_problems(approvers: list[str], code_owners: list[str], blocked: list[str]) -> list[str]:
    """F6.1: at least one code owner approved, and no agent account or merge-bot approved.

    ``approvers`` comes from the GitLab MR approvals API (usernames); ``blocked`` lists the agent
    service accounts and the merge-bot."""
    found = []
    bad = sorted(set(approvers) & set(blocked))
    if bad:
        found.append(f"approved by an agent or bot account: {', '.join(bad)}")
    if not set(approvers) & (set(code_owners) - set(blocked)):
        found.append("no code-owner approval")
    return found
