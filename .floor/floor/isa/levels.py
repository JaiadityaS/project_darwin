"""x86-64 micro-architecture levels (x86-64 psABI) and the CPUID features in each level."""

from __future__ import annotations

from collections.abc import Iterable

LEVEL_NAMES = {0: "none", 1: "x86-64-v1", 2: "x86-64-v2", 3: "x86-64-v3", 4: "x86-64-v4"}

# Feature names follow iced-x86 CpuidFeature. A feature in no set is an "extra":
# it is outside every level, so no level guarantees it (for example AES, AVX512_VNNI).
_LEVEL_SETS = {
    1: {
        "INTEL8086", "INTEL186", "INTEL286", "INTEL386", "INTEL486", "X64",
        "CPUID", "TSC", "MSR", "RDPMC", "SYSCALL", "SEP", "MULTIBYTENOP", "PAUSE",
        "CMOV", "CX8", "FPU", "FPU287", "FPU387", "FXSR", "MMX", "SSE", "SSE2", "CLFSH",
    },
    2: {"CMPXCHG16B", "POPCNT", "SSE3", "SSSE3", "SSE4_1", "SSE4_2"},
    3: {"AVX", "AVX2", "BMI1", "BMI2", "F16C", "FMA", "LZCNT", "MOVBE", "XSAVE"},
    4: {"AVX512F", "AVX512BW", "AVX512CD", "AVX512DQ", "AVX512VL"},
}
FEATURE_LEVEL = {name: level for level, names in _LEVEL_SETS.items() for name in names}

# Extras that cannot run below a level (for example a VEX-encoded VNNI instruction needs AVX).
_EXTRA_IMPLIES = (("AVX512", 4), ("AMX", 4), ("AVX10", 4), ("AVX_", 3), ("VAES", 3), ("VPCLMULQDQ", 3))


def level_name(level: int) -> str:
    return LEVEL_NAMES[level]


def parse_level(text: str) -> int:
    """Accepts 'x86-64-v3', 'v3' or '3'."""
    value = text.strip().lower().removeprefix("x86-64-").removeprefix("v")
    level = int(value)
    if level not in (1, 2, 3, 4):
        raise ValueError(f"unknown x86-64 level: {text!r}")
    return level


def classify(features: Iterable[str]) -> tuple[int, tuple[str, ...]]:
    """Returns (level, extras) for the CPUID features of one instruction."""
    level = 1
    extras = set()
    for name in features:
        known = FEATURE_LEVEL.get(name)
        if known is not None:
            level = max(level, known)
            continue
        extras.add(name)
        for prefix, implied in _EXTRA_IMPLIES:
            if name.startswith(prefix):
                level = max(level, implied)
    return level, tuple(sorted(extras))
