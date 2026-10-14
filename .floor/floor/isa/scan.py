"""Static CPU-floor scan of ELF files (PRD F2).

The floor of a build is the highest x86-64 level in the code that always loads,
joined with the lowest ggml CPU variant (the variant that the backend loader
falls back to on the oldest CPU).
"""

from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from elftools.elf.elffile import ELFFile

from .decode import DecodeStats, OpcodeStat, decode_region
from .elf import exec_regions, isa_needed
from .levels import level_name

ELF_MAGIC = b"\x7fELF"
VARIANT_RE = re.compile(r"^libggml-cpu-([A-Za-z0-9_]+)\.so")
MAX_EVIDENCE = 8
MAX_SOURCES = 20

# core        always loaded: executables, libwhisper, libggml-base, libggml, a single libggml-cpu
# variant     one ggml CPU backend variant; the loader picks the best one at run time
# build-tool  CMake probe binaries below CMakeFiles/; they never run in production
# distro      base-image libraries (glibc dispatches with ifunc); recorded, not counted
ROLES = ("core", "variant", "build-tool", "distro")


def classify_role(relpath: str) -> tuple[str, str | None]:
    """Returns (role, variant tag) for a path inside a build tree or an image layer."""
    path = "/" + relpath.replace("\\", "/").lstrip("/")
    if "/CMakeFiles/" in path:
        return "build-tool", None
    match = VARIANT_RE.match(path.rsplit("/", 1)[-1])
    if match:
        return "variant", match.group(1)
    return "core", None


@dataclass
class FileReport:
    path: str
    sha256: str
    size: int
    elf_type: str
    role: str
    variant: str | None = None
    level: int = 0
    extras: dict[str, int] = field(default_factory=dict)
    features: dict[str, int] = field(default_factory=dict)
    allowlisted: dict[str, int] = field(default_factory=dict)
    evidence: list[dict] = field(default_factory=list)
    instructions: int = 0
    invalid: int = 0
    isa_needed: list[str] | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["level"] = level_name(self.level)
        return data


def scan_file(path: str | os.PathLike, relpath: str | None = None, role: str | None = None) -> FileReport | None:
    """Scans one file. Returns None if it is not an x86-64 executable or shared object."""
    path = Path(path)
    with open(path, "rb") as fh:
        if fh.read(4) != ELF_MAGIC:
            return None
        fh.seek(0)
        digest = hashlib.sha256()
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
        size = fh.tell()
        fh.seek(0)
        return scan_stream(fh, relpath or path.name, size, digest.hexdigest(), role)


def scan_stream(fh, relpath: str, size: int, sha256: str, role: str | None = None) -> FileReport | None:
    """Scans an ELF file from a seekable binary stream."""
    variant = None
    if role is None:
        role, variant = classify_role(relpath)
    report = FileReport(path=relpath, sha256=sha256, size=size, elf_type="unknown", role=role, variant=variant)
    try:
        elf = ELFFile(fh)
        if elf["e_machine"] != "EM_X86_64" or elf["e_type"] not in ("ET_EXEC", "ET_DYN"):
            return None
        report.elf_type = elf["e_type"]
        stats = DecodeStats()
        for name, address, data in exec_regions(elf):
            decode_region(data, address, name, stats)
        report.isa_needed = isa_needed(elf)
    except Exception as exc:  # a damaged file must not stop the scan; the summary lists it
        report.error = f"{type(exc).__name__}: {exc}"
        return report
    _fill(report, stats)
    return report


def _fill(report: FileReport, stats: DecodeStats) -> None:
    report.instructions = stats.instructions
    report.invalid = stats.invalid
    counted = [st for st in stats.opcodes.values() if st.allow_reason is None]
    level = 1 if stats.opcodes else 0
    for st in counted:
        level = max(level, st.level)
    report.level = level

    features: Counter[str] = Counter()
    extras: Counter[str] = Counter()
    allowlisted: Counter[str] = Counter()
    for st in stats.opcodes.values():
        for name in st.features:
            features[name] += st.count
        if st.allow_reason is not None:
            allowlisted[st.mnemonic] += st.count
        else:
            for name in st.extras:
                extras[name] += st.count
    report.features = dict(sorted(features.items()))
    report.extras = dict(sorted(extras.items()))
    report.allowlisted = dict(sorted(allowlisted.items()))

    # Evidence: the most frequent opcode forms at the file level, then one example per extra.
    by_count = sorted(counted, key=lambda st: (-st.count, st.first_ip))
    chosen = [st for st in by_count if st.level == level][:MAX_EVIDENCE] if level > 1 else []
    seen = {name for st in chosen for name in st.extras}
    for st in by_count:
        if set(st.extras) - seen:
            chosen.append(st)
            seen.update(st.extras)
    report.evidence = [_evidence(st) for st in chosen]


def _evidence(st: OpcodeStat) -> dict:
    return {
        "instr": st.example,
        "mnemonic": st.mnemonic,
        "features": list(st.features),
        "level": level_name(st.level),
        "count": st.count,
        "first_addr": hex(st.first_ip),
        "region": st.region,
    }


def scan_path(root: str | os.PathLike, role: str | None = None) -> list[FileReport]:
    """Scans one file, or every regular file below a directory. Symbolic links are skipped."""
    root = Path(root)
    if root.is_file():
        found = [(root, root.name)]
    else:
        found = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for name in sorted(filenames):
                full = Path(dirpath, name)
                if not full.is_symlink() and full.is_file():
                    found.append((full, full.relative_to(root).as_posix()))
    reports = []
    for full, rel in found:
        try:
            report = scan_file(full, rel, role)
        except OSError as exc:
            file_role, variant = (role, None) if role else classify_role(rel)
            report = FileReport(path=rel, sha256="", size=0, elf_type="unknown", role=file_role,
                                variant=variant, error=f"{type(exc).__name__}: {exc}")
        if report is not None:
            reports.append(report)
    return reports


def summarize(reports: list[FileReport]) -> dict:
    """Joins file reports into the floor of one build (PRD F2.1)."""
    ok = [r for r in reports if r.error is None]
    core = [r for r in ok if r.role == "core"]
    variants = [r for r in ok if r.role == "variant"]
    level = max((r.level for r in core), default=0)
    sources = [r.path for r in core if r.level == level]
    baseline = min(variants, key=lambda r: (r.level, len(r.extras), r.path), default=None)
    if baseline is not None:
        if baseline.level > level:
            level, sources = baseline.level, [baseline.path]
        elif baseline.level == level:
            sources.append(baseline.path)
    floor_files = core + ([baseline] if baseline is not None else [])
    return {
        "floor": {
            "level": level_name(level),
            "extras": sorted({name for r in floor_files for name in r.extras}),
            "sources": sources[:MAX_SOURCES] if level > 1 else [],
        },
        "baseline_variant": baseline.variant if baseline is not None else None,
        "variants": {r.variant: level_name(r.level) for r in sorted(variants, key=lambda r: r.variant or "")},
        "highest_level_found": level_name(max((r.level for r in core + variants), default=0)),
        "files": {
            "scanned": len(reports),
            **{role: sum(1 for r in reports if r.role == role) for role in ROLES},
            "errors": [r.path for r in reports if r.error is not None],
        },
    }
