"""Canned inclusive config (PRD F4.3): a script, not an agent, applies it when the agent's fix fails.

It changes only paths in the agent allowlist, so the gate and the merge-bot treat it the same way:
- every `make <model>` / `make build` in .devops/*.Dockerfile gets CMAKE_ARGS with the canned flags
  (upstream's Makefile passes CMAKE_ARGS to cmake);
- every `cmake -B <dir>` configure command gets the flags;
- .floor/overrides/<artifact>.flags records them for the build.
The gate then re-verifies the branch.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

CANNED = {
    "GGML_NATIVE": "OFF",
    "GGML_BACKEND_DL": "ON",
    "GGML_CPU_ALL_VARIANTS": "ON",
    "BUILD_SHARED_LIBS": "ON",
}
_MAKE = re.compile(r"\bmake(?P<args>(?:[ \t]+(?!&&|\|\||;)[^ \t\n;&|\\]+)*)")
_CMAKE_ARGS = re.compile(r"""CMAKE_ARGS=(?:"(?P<dq>[^"]*)"|'(?P<sq>[^']*)'|(?P<bare>\S+))""")
_CONFIGURE = re.compile(r"\bcmake(?P<args>(?:[ \t]+(?!&&|\|\||;)[^ \t\n;&|\\]+)*)")


def flags_text(flags: dict[str, str] = CANNED) -> str:
    return " ".join(f"-D{key}={value}" for key, value in flags.items())


def merge(existing: str) -> str:
    """Keeps the other -D flags; the canned keys win."""
    kept = [token for token in shlex.split(existing)
            if not (token.startswith("-D") and token[2:].split("=", 1)[0].split(":", 1)[0] in CANNED)]
    return " ".join(kept + [flags_text()])


def _patch_make(match: re.Match) -> str:
    args = match.group("args")
    found = _CMAKE_ARGS.search(args)
    if found:
        old = found.group("dq") or found.group("sq") or found.group("bare") or ""
        args = args[:found.start()] + f'CMAKE_ARGS="{merge(old)}"' + args[found.end():]
    else:
        args = f' CMAKE_ARGS="{flags_text()}"' + args
    return "make" + args


def _patch_configure(match: re.Match) -> str:
    args = match.group("args")
    tokens = args.split()
    if "--build" in tokens or "-B" not in tokens and not any(t.startswith("-B") for t in tokens):
        return match.group(0)  # a build or install step, not a configure step
    kept = " ".join(t for t in tokens if not (t.startswith("-D") and t[2:].split("=", 1)[0].split(":", 1)[0] in CANNED))
    return f"cmake {kept} {flags_text()}"


def patch_dockerfile(text: str) -> str:
    out = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            out.append(line)
            continue
        line = _MAKE.sub(lambda m: _patch_make(m) if m.group("args").strip() else m.group(0), line)
        line = _CONFIGURE.sub(_patch_configure, line)
        out.append(line)
    return "".join(out)


def apply(root: str | Path = ".", dockerfiles: list[str] | None = None, artifact: str = "main") -> list[str]:
    """Applies the canned config under ``root``. Returns the changed paths (relative to root)."""
    root = Path(root)
    changed = []
    targets = dockerfiles or sorted(str(p.relative_to(root).as_posix()) for p in (root / ".devops").glob("*.Dockerfile"))
    for rel in targets:
        path = root / rel
        text = path.read_text(encoding="utf-8")
        new = patch_dockerfile(text)
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            changed.append(rel)
    override = root / ".floor" / "overrides" / f"{artifact}.flags"
    content = flags_text() + "\n"
    if not override.exists() or override.read_text(encoding="utf-8") != content:
        override.parent.mkdir(parents=True, exist_ok=True)
        override.write_text(content, encoding="utf-8", newline="\n")
        changed.append(override.relative_to(root).as_posix())
    return changed
