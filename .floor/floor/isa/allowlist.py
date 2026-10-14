"""Instructions that a static scan finds but that do not raise the CPU floor (PRD F2.2).

Every entry needs a reason and a unit test (tests/test_isa.py). The QEMU runs (F3)
corroborate the list. Keys are iced-x86 mnemonic names.
"""

import re

_CET_NOP = (
    "CET instruction in the hint-NOP opcode space. CPUs without CET run it as a NOP, "
    "so it cannot cause an illegal-instruction fault."
)

ALLOWLIST = {
    "TZCNT": (
        "Encoded as 'rep bsf'. CPUs without BMI1 ignore the rep prefix and run BSF. "
        "Compilers emit it on purpose for generic x86-64; the result is the same for non-zero input."
    ),
    "ENDBR64": _CET_NOP,
    "ENDBR32": _CET_NOP,
    "RDSSPD": _CET_NOP + " glibc uses it in setjmp and longjmp.",
    "RDSSPQ": _CET_NOP + " glibc uses it in setjmp and longjmp.",
    "XGETBV": (
        "Used only in CPU feature detection, after CPUID reports OSXSAVE. "
        "It decides which code to run; it is never on the compute path."
    ),
}

# Function-scoped entries: the mnemonic is allowed only inside functions whose symbol
# matches the pattern. The scan needs symbols (.symtab or .dynsym) to apply them.
GUARDED = {
    "LZCNT": (
        (re.compile(r"^drflac_"), (
            "dr_flac (in miniaudio) runs LZCNT only after its own CPUID check for ABM/LZCNT, "
            "and uses a portable count-leading-zeros path on other CPUs."
        )),
    ),
}


def guarded_reason(mnemonic: str, function: str | None) -> str | None:
    """Returns the reason when a function-scoped entry allows ``mnemonic`` in ``function``."""
    if function is None:
        return None
    for pattern, reason in GUARDED.get(mnemonic, ()):
        if pattern.match(function):
            return reason
    return None
