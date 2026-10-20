"""The IDs in brackets: every ID that a Rieux file cites is in .floor/DECISIONS.md."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / ".floor" / "DECISIONS.md"
# The Rieux files of the GitLab project. Everything else there is whisper.cpp.
PRODUCT = (".floor", ".gitlab", ".gitlab-ci.yml", "deploy", "infra", "README.md")
SKIP_DIRS = {"__pycache__", ".pytest_cache", "floor.egg-info"}
SKIP_SUFFIXES = {".json", ".wav", ".png", ".bin", ".pyc"}

# Requirements, acceptance checks, plan sections, decisions and plan terms.
ID = re.compile(r"(?<![\w.-])(D-\d{3}|AC-F\d+[a-z]?|NFR-\d+|F\d+(?:\.\d+)?|§\d+(?:\.\d+)?|H-\d|R\d|G\d)(?![\w-])")
# IDs of the team's working files, which are not in this project.
INTERNAL = re.compile(r"\bT-\d{2,3}\b|\bPRD\b|\bDECISIONS D-|\bG-\d\b")


def product_files():
    for name in PRODUCT:
        path = ROOT / name
        if path.is_file():
            yield path
        elif path.is_dir():
            for p in sorted(path.rglob("*")):
                if p.is_file() and p.suffix not in SKIP_SUFFIXES and not SKIP_DIRS & set(p.relative_to(ROOT).parts):
                    yield p


def texts():
    for p in product_files():
        try:
            yield p.relative_to(ROOT).as_posix(), p.read_text("utf-8")
        except UnicodeDecodeError:
            continue


def defined():
    ids = set()
    for line in DECISIONS.read_text("utf-8").splitlines():
        m = re.match(r"\| ([^|`]+?) \|", line) or re.match(r"### (D-\d{3}) ", line)
        if m and ID.fullmatch(m.group(1)):
            ids.add(m.group(1))
    return ids


def test_the_decisions_file_defines_ids():
    ids = defined()
    assert {"F4.3", "AC-F4a", "NFR-7", "§9.2", "D-010", "D-033", "H-1", "R2"} <= ids
    heads = re.findall(r"^### (D-\d{3}) ", DECISIONS.read_text("utf-8"), re.M)
    assert len(heads) == len(set(heads))


def test_every_cited_id_is_defined():
    ids = defined()
    missing = sorted({f"{name}: {m}" for name, text in texts() for m in ID.findall(text) if m not in ids})
    assert missing == []


def test_no_internal_ids():
    found = [f"{name}:{n}: {line.strip()[:80]}" for name, text in texts()
             for n, line in enumerate(text.splitlines(), 1) if INTERNAL.search(line)]
    assert found == []


def test_the_id_pattern():
    text = "(F4.1 to F4.3, D-018) AC-F4a NFR-7 §13.2 H-1 R2 G7. GGML_TYPE_F16 F16C 0xF3 AVX512F v1.1.0"
    assert ID.findall(text) == ["F4.1", "F4.3", "D-018", "AC-F4a", "NFR-7", "§13.2", "H-1", "R2", "G7"]
    # Built from parts, so this file does not cite them.
    assert INTERNAL.search("task T" + "-61") and INTERNAL.search("P" + "RD F12.3")
    assert not INTERNAL.search("DECISIONS.md")
