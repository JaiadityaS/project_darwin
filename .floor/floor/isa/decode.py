"""Linear-sweep x86-64 decoding with statistics per opcode form."""

from __future__ import annotations

from dataclasses import dataclass, field

from iced_x86 import Code, CpuidFeature, Decoder, Formatter, FormatterSyntax, Instruction, Mnemonic

from .allowlist import ALLOWLIST
from .levels import classify


def _constant_names(namespace) -> dict[int, str]:
    names: dict[int, str] = {}
    for name in dir(namespace):
        if name.startswith("_"):
            continue
        value = getattr(namespace, name)
        if isinstance(value, int) and not isinstance(value, bool):
            names.setdefault(value, name)
    return names


FEATURE_NAMES = _constant_names(CpuidFeature)
MNEMONIC_NAMES = _constant_names(Mnemonic)
_FORMATTER = Formatter(FormatterSyntax.INTEL)


@dataclass
class OpcodeStat:
    """All instructions in one file that share one opcode form (an iced-x86 Code)."""

    mnemonic: str
    features: tuple[str, ...]
    level: int
    extras: tuple[str, ...]
    allow_reason: str | None
    example: str
    first_ip: int
    region: str
    count: int = 1


@dataclass
class DecodeStats:
    opcodes: dict[int, OpcodeStat] = field(default_factory=dict)
    instructions: int = 0
    invalid: int = 0


def decode_region(data: bytes, base: int, region: str, stats: DecodeStats | None = None) -> DecodeStats:
    """Decodes one executable region and adds its opcode forms to ``stats``."""
    if stats is None:
        stats = DecodeStats()
    opcodes = stats.opcodes
    decoder = Decoder(64, data, ip=base)
    instr = Instruction()
    invalid_code = Code.INVALID
    count = 0
    invalid = 0
    while decoder.can_decode:
        decoder.decode_out(instr)
        count += 1
        code = instr.code
        if code == invalid_code:
            invalid += 1
            continue
        stat = opcodes.get(code)
        if stat is not None:
            stat.count += 1
            continue
        features = tuple(FEATURE_NAMES.get(f, f"FEATURE_{f}") for f in instr.cpuid_features())
        mnemonic = MNEMONIC_NAMES.get(instr.mnemonic, f"MNEMONIC_{instr.mnemonic}")
        level, extras = classify(features)
        opcodes[code] = OpcodeStat(
            mnemonic=mnemonic,
            features=features,
            level=level,
            extras=extras,
            allow_reason=ALLOWLIST.get(mnemonic),
            example=_FORMATTER.format(instr),
            first_ip=instr.ip,
            region=region,
        )
    stats.instructions += count
    stats.invalid += invalid
    return stats
