"""Path allowlist (PRD F4.2, §5, §10.1). Defense in depth: code-owner approval is the main control.

- An agent MR may change only AGENT_ALLOWED paths. None of them has a code owner.
- Agents never change engine code.
- The merge-bot may merge only when no code-owned path changed.
"""

from __future__ import annotations

import re
import subprocess

AGENT_ALLOWED = ("deploy/**", ".devops/*.Dockerfile", ".floor/overrides/**")
ENGINE = ("src/**", "ggml/**", "include/**", "examples/**")
CODE_OWNED = (
    ".floor/policy.yml",
    ".floor/policy.schema.json",
    ".floor/floor/**",          # the Judge and the gate scripts
    ".floor/pyproject.toml",
    ".floor/notices/**",
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


def changed_files(base: str, head: str = "HEAD") -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"], check=True,
                         capture_output=True, text=True, encoding="utf-8").stdout
    return [line for line in out.splitlines() if line]
