"""Path allowlist (PRD F4.2, §5, §10.1). Defense in depth: code-owner approval is the main control.

- An agent MR may change only AGENT_ALLOWED paths. None of them has a code owner.
- Agents never change engine code.
- The merge-bot may merge only when no code-owned path changed.
"""

from __future__ import annotations

import re
import subprocess

import requests

AGENT_ALLOWED = ("deploy/**", ".devops/*.Dockerfile", ".floor/overrides/**")
ENGINE = ("src/**", "ggml/**", "include/**", "examples/**")
CODE_OWNED = (
    ".floor/policy.yml",
    ".floor/policy.schema.json",
    ".floor/floor/**",          # the Judge and the gate scripts
    ".floor/pyproject.toml",
    ".floor/notices/**",
    ".floor/flows/**",          # the flow definitions (AI Catalog, T-03, T-40)
    "CODEOWNERS",
    ".gitlab/CODEOWNERS",
    ".gitlab-ci.yml",
    ".gitlab/ci/**",
)


def _regex(pattern: str) -> re.Pattern:
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(path: str, patterns) -> bool:
    return any(_regex(p).match(path) for p in patterns)


def check(changed: list[str], actor: str) -> list[str]:
    """Problems for ``actor`` ("agent" or "merge-bot"). Empty list = allowed."""
    problems = []
    for path in sorted(set(changed)):
        if matches(path, ENGINE) and actor == "agent":
            problems.append(f"{path}: engine code (agents never change it)")
        elif actor == "agent" and not matches(path, AGENT_ALLOWED):
            problems.append(f"{path}: outside the agent allowlist")
        elif actor == "merge-bot" and matches(path, CODE_OWNED):
            problems.append(f"{path}: code-owned (needs a code owner, not the merge-bot)")
    return problems


def mr_author(api_url: str, project_id: str, iid: str, timeout: float = 20) -> str | None:
    """The username of the MR author from the GitLab API (a public project needs no token).
    None when the API gives no answer."""
    try:
        response = requests.get(f"{api_url}/projects/{project_id}/merge_requests/{iid}", timeout=timeout)
        response.raise_for_status()
        return response.json()["author"]["username"] or None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def pipeline_actor(env, author=None) -> tuple[str, list[str]]:
    """("human" or "agent", the reasons). Deny by default (D-014): each user must be in FLOOR_HUMANS.

    The users are the pipeline user and, on an MR pipeline, the MR author. So a human who runs the
    pipeline of an agent MR again does not turn off the agent allowlist (D-014, gap 1).
    """
    humans = set(env.get("FLOOR_HUMANS", "").split())
    users = [("pipeline user", env.get("GITLAB_USER_LOGIN") or None)]
    if env.get("CI_MERGE_REQUEST_IID"):
        found = (author or mr_author)(env.get("CI_API_V4_URL", ""), env.get("CI_MERGE_REQUEST_PROJECT_ID", ""),
                                      env["CI_MERGE_REQUEST_IID"])
        users.append(("MR author", found))
    actor, reasons = "human", []
    for role, user in users:
        if user in humans:
            reasons.append(f"{role} {user}: a human (FLOOR_HUMANS)")
        else:
            actor = "agent"
            reasons.append(f"{role} {user}: counts as an agent" if user else f"{role}: unknown, counts as an agent")
    return actor, reasons


def changed_files(base: str, head: str = "HEAD") -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"], check=True,
                         capture_output=True, text=True, encoding="utf-8").stdout
    return [line for line in out.splitlines() if line]
