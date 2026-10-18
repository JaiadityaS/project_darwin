"""Canned inclusive config (PRD F4.3): a script, not an agent, applies it when the agent's fix fails.

It changes only paths in the agent allowlist, so the gate and the merge-bot treat it the same way:
- every `make` command in a RUN instruction of .devops/*.Dockerfile gets CMAKE_ARGS with the canned
  flags (upstream's Makefile passes CMAKE_ARGS to cmake);
- every `cmake -B <dir>` configure command gets the flags;
- .floor/overrides/<artifact>.flags records them for the build.
The patch reads each RUN instruction as shell words. Quotes, escapes and line continuations stay as
they are, and a `make` that is not a command (for example a package name in an install list) stays.
The gate then re-verifies the branch. When `pending` finds nothing to change, the fallback has already
run on the branch: if the gate still fails, `floor notice-draft` writes a draft notice (F4.5).
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

CANNED = {
    "GGML_NATIVE": "OFF",
    "GGML_BACKEND_DL": "ON",
    "GGML_CPU_ALL_VARIANTS": "ON",
    "BUILD_SHARED_LIBS": "ON",
}
_KEY = r"-D(?:" + "|".join(CANNED) + r")(?::\w+)?="
_CANNED_WORD = re.compile(_KEY)
_CANNED_IN_ARGS = re.compile(r"(?:^|[ \t]+)" + _KEY + r"\S*")
_DOUBLE = re.compile(r'"((?:[^"\\]|\\.)*)"', re.DOTALL)
_SINGLE = re.compile(r"'([^']*)'")
_RUN = re.compile(r"[ \t]*RUN\b", re.IGNORECASE)
_ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=")
_OPERATORS = ("&&", "||", ";;", ";", "|", "&", "(", ")")
_STOP = " \t\r\n;&|()"
_CONTINUATION = ("\\\n", "\\\r\n")
# After these words a command still starts: `then make ...`, `if make ...`.
_KEYWORDS = {"!", "{", "if", "then", "else", "elif", "do", "while", "until", "time"}


def flags_text(flags: dict[str, str] = CANNED) -> str:
    return " ".join(f"-D{key}={value}" for key, value in flags.items())


def merge(existing: str) -> str:
    """Keeps the other CMake arguments as they are (with their quotes and escapes); the canned keys win."""
    kept = re.sub(r"[ \t]*\\$", "", _CANNED_IN_ARGS.sub("", existing).strip())
    return f"{kept} {flags_text()}" if kept else flags_text()


def _merge_assignment(word: str) -> str:
    """NAME=value with the canned flags merged into the value. The value keeps its quotes."""
    name, value = word.split("=", 1)
    for pattern, quote in ((_DOUBLE, '"'), (_SINGLE, "'")):
        found = pattern.fullmatch(value)
        if found:
            return f"{name}={quote}{merge(found.group(1))}{quote}"
    if re.search(r"""["'\\]""", value):
        return f'{name}={value}" {flags_text()}"'  # mixed quotes: the shell joins the two parts
    return f'{name}="{merge(value)}"'


def _skip_quoted(text: str, i: int) -> int:
    """The index after the closing double quote. ``i`` is the index after the opening quote."""
    while i < len(text) and text[i] != '"':
        i += 2 if text[i] == "\\" else 1
    return min(i + 1, len(text))


def _skip_parens(text: str, i: int) -> int:
    """The index after the `)` that closes `$(`. ``i`` is the index after `$(`."""
    depth = 1
    while i < len(text) and depth:
        if text[i] in "()":
            depth += 1 if text[i] == "(" else -1
            i += 1
        else:
            i = max(_word_end(text, i, "()"), i + 1)
    return i


def _word_end(text: str, i: int, stop: str = _STOP) -> int:
    """The index after the shell word at ``i``. Quotes, escapes, `...` and $(...) stay in the word."""
    while i < len(text) and text[i] not in stop and not text.startswith(_CONTINUATION, i):
        if text[i] == "\\" or text.startswith((">&", "<&"), i):
            i += 2
        elif text[i] in "'`":
            close = text.find(text[i], i + 1)
            i = len(text) if close < 0 else close + 1
        elif text[i] == '"':
            i = _skip_quoted(text, i + 1)
        elif text.startswith("$(", i):
            i = _skip_parens(text, i + 2)
        else:
            i += 1
    return min(i, len(text))


def _tokens(text: str) -> list[tuple[bool, int, int]]:
    """The shell tokens of one RUN instruction: (is an operator, start, end)."""
    tokens, i = [], 0
    while i < len(text):
        if text[i] in " \t\r\n" or text.startswith(_CONTINUATION, i):
            i += 1
        elif text[i] == "#":  # a comment to the end of the line
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
        elif text[i] in ";&|()":
            operator = next(op for op in _OPERATORS if text.startswith(op, i))
            tokens.append((True, i, i + len(operator)))
            i += len(operator)
        else:
            end = max(_word_end(text, i), i + 1)
            tokens.append((False, i, end))
            i = end
    return tokens


def _commands(text: str) -> list[tuple[list[tuple[int, int]], list[tuple[int, int]]]]:
    """(assignments, words) of each simple command in one RUN instruction. words[0] is the command name."""
    tokens = _tokens(text)[1:]  # tokens[0] is RUN
    while tokens and not tokens[0][0] and text.startswith("--", tokens[0][1]):
        tokens.pop(0)  # RUN flags such as --mount=...
    commands, assignments, words = [], [], []
    for operator, start, end in tokens + [(True, len(text), len(text))]:
        word = text[start:end]
        if operator:
            if words:
                commands.append((assignments, words))
            assignments, words = [], []
        elif words:
            words.append((start, end))
        elif _ASSIGNMENT.match(word):
            assignments.append((start, end))
        elif word not in _KEYWORDS:
            words.append((start, end))
    return commands


def _make_edit(text: str, assignments: list, words: list) -> tuple[int, int, str]:
    for start, end in words[1:] + assignments:  # an argument overrides the environment in make
        if text.startswith("CMAKE_ARGS=", start):
            return start, end, _merge_assignment(text[start:end])
    end = words[0][1]
    return end, end, f' CMAKE_ARGS="{flags_text()}"'


def _configure_edit(text: str, words: list) -> tuple[int, int, str] | None:
    args = [text[start:end] for start, end in words[1:]]
    if "--build" in args or not any(arg.startswith("-B") for arg in args):
        return None  # a build or install step, not a configure step
    # Each kept word keeps the gap before it. When the words before it go, it keeps their last
    # line break, so the other lines of the command keep their layout.
    out, last, line_break = [text[slice(*words[0])]], words[0][1], None
    for (start, end), arg in zip(words[1:], args):
        gap, last = text[last:start], end
        if _CANNED_WORD.match(arg.strip("\"'")):
            line_break = gap if "\n" in gap else line_break
            continue
        out.append((gap if "\n" in gap or line_break is None else line_break) + arg)
        line_break = None
    return words[0][0], words[-1][1], "".join(out) + " " + flags_text()


def _patch_run(text: str) -> str:
    edits = []
    for assignments, words in _commands(text):
        name = text[slice(*words[0])]
        edit = (_make_edit(text, assignments, words) if name == "make"
                else _configure_edit(text, words) if name == "cmake" else None)
        if edit:
            edits.append(edit)
    for start, end, new in sorted(edits, reverse=True):
        text = text[:start] + new + text[end:]
    return text


def _runs(text: str) -> list[tuple[int, int]]:
    """(start, end) of each RUN instruction. A line that ends with a backslash continues the
    instruction; an empty line or a comment line does not end it (Dockerfile rules)."""
    spans, start, pos, continued = [], None, 0, False
    for line in text.splitlines(keepends=True):
        code = line.strip()
        if code and not code.startswith("#"):
            if not continued:
                start = pos if _RUN.match(line) else None
            continued = code.endswith("\\")
        pos += len(line)
        if start is not None and not continued:
            spans.append((start, pos))
            start = None
    if start is not None:
        spans.append((start, pos))
    return spans


def patch_dockerfile(text: str) -> str:
    out, last = [], 0
    for start, end in _runs(text):
        out += [text[last:start], _patch_run(text[start:end])]
        last = end
    return "".join(out) + text[last:]


def _changes(root: Path, dockerfiles: list[str] | None, artifact: str) -> dict[str, str]:
    """{path relative to root: new text} for each file that the canned config changes."""
    changes = {}
    targets = dockerfiles or sorted(str(p.relative_to(root).as_posix()) for p in (root / ".devops").glob("*.Dockerfile"))
    for rel in targets:
        text = (root / rel).read_text(encoding="utf-8")
        new = patch_dockerfile(text)
        if new != text:
            changes[rel] = new
    override = root / ".floor" / "overrides" / f"{artifact}.flags"
    content = flags_text() + "\n"
    if not override.exists() or override.read_text(encoding="utf-8") != content:
        changes[override.relative_to(root).as_posix()] = content
    return changes


def pending(root: str | Path = ".", dockerfiles: list[str] | None = None, artifact: str = "main") -> list[str]:
    """The paths that `apply` would change. Empty = the canned config is already on the branch (F4.5)."""
    return list(_changes(Path(root), dockerfiles, artifact))


def apply(root: str | Path = ".", dockerfiles: list[str] | None = None, artifact: str = "main") -> list[str]:
    """Applies the canned config under ``root``. Returns the changed paths (relative to root)."""
    root = Path(root)
    changes = _changes(root, dockerfiles, artifact)
    for rel, text in changes.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    return list(changes)


def _diff_lines(lines) -> str:
    out = []
    for line in lines:
        out.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
    return "".join(out)


def patch(root: str | Path = ".", dockerfiles: list[str] | None = None, artifact: str = "main") -> str:
    """The changes of `apply` as a patch for `git apply`. Changes no file. Empty = nothing to change.

    CI has no token that can push to the branch (D-010, D-018), so the fallback job keeps this patch as an
    artifact, and the flow or a human commits it. The next pipeline of the branch is the gate's re-check.
    """
    root = Path(root)
    out = []
    for rel, new in _changes(root, dockerfiles, artifact).items():
        old_path = root / rel
        old = old_path.read_text(encoding="utf-8") if old_path.exists() else None
        out.append(f"diff --git a/{rel} b/{rel}\n")
        if old is None:
            out.append("new file mode 100644\n")
        out.append(_diff_lines(difflib.unified_diff((old or "").splitlines(keepends=True), new.splitlines(keepends=True),
                                                    "/dev/null" if old is None else f"a/{rel}", f"b/{rel}")))
    return "".join(out)
