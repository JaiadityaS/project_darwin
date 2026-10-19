"""Policy ratchet (PRD F1.2): a stricter policy needs a normal MR; a looser one needs a merged notice.

"Merged" means the notice file is already on the target branch. So the notice MR merges
first, and the policy MR that loosens the floor follows it.

The "Approved by" line is text, and an agent can write text. So in CI a notice counts only when the
GitLab approvals of its merged MR show a code owner who is a human, and no other account (F6.1,
`approval`).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable

import yaml

from . import notice, policy
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


def check(old: dict, new: dict, notices: dict[str, str],
          verify: Callable[[str], list[str]] | None = None) -> dict:
    """``notices`` maps a notice file name to its text (only notices on the target branch).

    ``verify`` maps a notice name to its problems (see ``approval``). A notice with a problem covers
    nothing, and the row of a looser change lists it under "refused"."""
    covered: dict[str, list[str]] = {}
    for name, text in sorted(notices.items()):
        for dimension in notice_dimensions(text) or ():
            covered.setdefault(dimension, []).append(name)
    rows = compare(old, new)
    found: dict[str, list[str]] = {}
    for row in rows:
        if row["direction"] == "looser":
            names = covered.get(row["dimension"], [])
            if verify:
                for name in names:
                    if name not in found:
                        found[name] = verify(name)
                if refused := {name: found[name] for name in names if found[name]}:
                    row["refused"] = refused
                names = [name for name in names if not found[name]]
            row["notices"] = names
    blocked = [row for row in rows if row["direction"] == "looser" and not row["notices"]]
    return {"ok": not blocked, "changes": rows, "blocked": blocked}


def approvers(sha: str, default_branch: str, get: Callable[[str], object]) -> tuple[str, list[str]]:
    """(the merged MR into the default branch that has commit ``sha``, the usernames that approved it).

    ``get`` reads one GitLab API path of the project and returns the JSON. A public project needs no
    token for these two paths. LookupError when no such MR exists."""
    for mr in get(f"/repository/commits/{sha}/merge_requests") or []:
        if mr.get("state") == "merged" and mr.get("target_branch") == default_branch:
            doc = get(f"/merge_requests/{mr['iid']}/approvals") or {}
            return mr["web_url"], [a["user"]["username"] for a in doc.get("approved_by") or []]
    raise LookupError(f"no merged MR into {default_branch} has commit {sha[:8]}")


def code_owners(text: str, path: str = f"/{NOTICE_DIR}/") -> list[str]:
    """The owners of ``path`` in a CODEOWNERS text: the last line for exactly that path wins."""
    owners: list[str] = []
    for line in text.splitlines():
        words = line.split("#", 1)[0].split()
        if words and words[0] == path:
            owners = [w.lstrip("@") for w in words[1:]]
    return owners


def approval(ref: str, default_branch: str, get: Callable[[str], object], humans: list[str],
             notice_dir: str = NOTICE_DIR, codeowners: str = ".gitlab/CODEOWNERS") -> Callable[[str], list[str]]:
    """``verify`` for ``check``: the problems of the merged MR that added a notice on ``ref``.

    Deny by default, as `floor paths` (D-014): every approver must be in ``humans`` (FLOOR_HUMANS),
    one of them must own the notice folder in CODEOWNERS (as it is on ``ref``), and the "Approved by"
    line must name one of them. If git or the API gives no answer, the notice does not count."""
    owners = code_owners(_git("show", f"{ref}:{codeowners}")) if _has_tree(ref, codeowners) else []

    def verify(name: str) -> list[str]:
        path = f"{notice_dir}/{name}"
        try:
            sha = _git("log", "--diff-filter=A", "--format=%H", "-1", ref, "--", path).strip()
            if not sha:
                return [f"no commit on {ref} added {path}"]
            mr, approved = approvers(sha, default_branch, get)
        except subprocess.CalledProcessError as exc:
            return [f"git failed: {exc.stderr.strip()}"]
        except (LookupError, OSError, ValueError, KeyError, TypeError) as exc:
            return [f"no approvals from the GitLab API ({exc})"]
        found = notice.approval_problems(approved, owners, [a for a in approved if a not in humans])
        line = _APPROVED_BY.search(_git("show", f"{ref}:{path}"))
        named = set(re.findall(r"[\w.-]+", line.group(1))) if line else set()
        if approved and not named & set(approved):
            found.append(f"the 'Approved by' line names none of the approvers ({', '.join(approved)})")
        return [f"{mr}: {problem}" for problem in found]

    return verify


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
