"""Policy ratchet (PRD F1.2): a stricter policy needs a normal MR; a looser one needs a merged notice.

"Merged" means the notice file is already on the target branch. So the notice MR merges
first, and the policy MR that loosens the floor follows it.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from . import policy
from .isa.levels import parse_level

NOTICE_DIR = ".floor/notices"
DIMENSIONS = {"cpu": "cpu", "memory_mb": "memory", "connectivity": "connectivity", "language": "language"}
# [ \t]*, not \s*: an empty field must not take the text of the next line.
_FLOOR_CHANGE = re.compile(r"^Floor change:[ \t]*(\S.*)$", re.MULTILINE)
_APPROVED_BY = re.compile(r"^Approved by:[ \t]*(\S.*)$", re.MULTILINE)
_WORD = re.compile(r"[a-z_]+")


def _scopes(doc: dict) -> dict[str, dict]:
    """The top-level policy plus the resolved policy of each artifact."""
    scopes = {"": policy.for_artifact(doc, None)}
    for name in doc.get("artifacts") or {}:
        scopes[name] = policy.for_artifact(doc, name)
    return scopes


def _changes(old: dict, new: dict) -> list[tuple[str, str, object, object, str]]:
    """(dimension, field, old, new, direction) for each field that moved."""
    rows = []

    def add(dimension, field, a, b, looser):
        if a != b:
            rows.append((dimension, field, a, b, "looser" if looser else "stricter"))

    oc, nc = old.get("cpu", {}), new.get("cpu", {})
    a, b = oc.get("x86_64_min_level"), nc.get("x86_64_min_level")
    if a and b:
        add("cpu", "x86_64_min_level", a, b, parse_level(b) > parse_level(a))
    removed = sorted(set(oc.get("emulate") or ()) - set(nc.get("emulate") or ()))
    added = sorted(set(nc.get("emulate") or ()) - set(oc.get("emulate") or ()))
    if removed:
        add("cpu", "emulate", removed, None, True)
    if added:
        add("cpu", "emulate", None, added, False)

    om, nm = old.get("memory_mb") or {}, new.get("memory_mb") or {}
    for model in sorted(set(om) | set(nm)):
        a, b = om.get(model), nm.get(model)
        add("memory", f"memory_mb.{model}", a, b, a is not None and (b is None or b > a))

    a = bool((old.get("connectivity") or {}).get("offline_required"))
    b = bool((new.get("connectivity") or {}).get("offline_required"))
    add("connectivity", "offline_required", a, b, a and not b)

    a = bool((old.get("language") or {}).get("gate"))
    b = bool((new.get("language") or {}).get("gate"))
    add("language", "language.gate", a, b, a and not b)
    return rows


def compare(old: dict, new: dict) -> list[dict]:
    """Every change between two policies, for each scope (top level and each artifact)."""
    old_scopes, new_scopes = _scopes(old), _scopes(new)
    rows = []
    for scope in sorted(set(old_scopes) | set(new_scopes)):
        a = old_scopes.get(scope, old_scopes[""])
        b = new_scopes.get(scope, new_scopes[""])
        for dimension, field, before, after, direction in _changes(a, b):
            rows.append({"artifact": scope or None, "dimension": dimension, "field": field,
                         "from": before, "to": after, "direction": direction})
    return rows


def notice_dimensions(text: str) -> set[str] | None:
    """The dimensions a notice covers, or None if it is not a complete notice (no approver)."""
    approved = _APPROVED_BY.search(text)
    change = _FLOOR_CHANGE.search(text)
    if not approved or not change or approved.group(1).startswith("<"):
        return None
    words = set(_WORD.findall(change.group(1).lower()))
    return {dimension for key, dimension in DIMENSIONS.items() if key in words or dimension in words}


def check(old: dict, new: dict, notices: dict[str, str]) -> dict:
    """``notices`` maps a notice file name to its text (only notices on the target branch)."""
    covered: dict[str, list[str]] = {}
    for name, text in sorted(notices.items()):
        for dimension in notice_dimensions(text) or ():
            covered.setdefault(dimension, []).append(name)
    rows = compare(old, new)
    for row in rows:
        if row["direction"] == "looser":
            row["notices"] = covered.get(row["dimension"], [])
    blocked = [row for row in rows if row["direction"] == "looser" and not row["notices"]]
    return {"ok": not blocked, "changes": rows, "blocked": blocked}


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True, encoding="utf-8").stdout


def from_git(ref: str, policy_path: str = ".floor/policy.yml", notice_dir: str = NOTICE_DIR) -> tuple[dict, dict]:
    """The policy and the notices as they are at ``ref`` (the target branch)."""
    old = yaml.safe_load(_git("show", f"{ref}:{policy_path}"))
    names = [line for line in _git("ls-tree", "--name-only", f"{ref}:{notice_dir}").splitlines()
             if line.endswith(".md")] if _has_tree(ref, notice_dir) else []
    return old, {name: _git("show", f"{ref}:{notice_dir}/{name}") for name in names}


def _has_tree(ref: str, path: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{ref}:{path}"], capture_output=True).returncode == 0


def from_dir(path: str | Path) -> dict[str, str]:
    folder = Path(path)
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(folder.glob("*.md"))} if folder.is_dir() else {}
