"""Linear-sweep x86-64 decoding with statistics per opcode form."""

from __future__ import annotations

from dataclasses import dataclass, field

from iced_x86 import Code, CpuidFeature, Decoder, Formatter, FormatterSyntax, Instruction, Mnemonic

from .allowlist import ALLOWLIST, GUARDED, guarded_reason
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
GUARDED_MNEMONICS = frozenset(getattr(Mnemonic, name) for name in GUARDED)
MAX_SAMPLES = 32


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
    sample_ips: list[int] = field(default_factory=list)


@dataclass
class DecodeStats:
    opcodes: dict[int, OpcodeStat] = field(default_factory=dict)
    instructions: int = 0
    invalid: int = 0


def decode_region(data: bytes, base: int, region: str, stats: DecodeStats | None = None,
                  symbols=None) -> DecodeStats:
    """Decodes one executable region and adds its opcode forms to ``stats``.

    With ``symbols`` (an elf.Symbols), function-scoped allowlist entries apply. An allowed
    instruction is counted under its own key, apart from the same opcode form elsewhere.
    """
    if stats is None:
        stats = DecodeStats()
    opcodes = stats.opcodes
    decoder = Decoder(64, data, ip=base)
    instr = Instruction()
    invalid_code = Code.INVALID
    count = 0
    invalid = 0
    guarded = GUARDED_MNEMONICS if symbols is not None else frozenset()
    while decoder.can_decode:
        decoder.decode_out(instr)
        count += 1
        code = instr.code
        if code == invalid_code:
            invalid += 1
            continue
        allow = None
        if guarded and instr.mnemonic in guarded:
            allow = guarded_reason(MNEMONIC_NAMES[instr.mnemonic], symbols.lookup(instr.ip))
            if allow is not None:
                code = -1 - code
        stat = opcodes.get(code)
        if stat is not None:
            stat.count += 1
            if len(stat.sample_ips) < MAX_SAMPLES:
                stat.sample_ips.append(instr.ip)
            continue
        features = tuple(FEATURE_NAMES.get(f, f"FEATURE_{f}") for f in instr.cpuid_features())
        mnemonic = MNEMONIC_NAMES.get(instr.mnemonic, f"MNEMONIC_{instr.mnemonic}")
        level, extras = classify(features)
        opcodes[code] = OpcodeStat(
            mnemonic=mnemonic,
            features=features,
            level=level,
            extras=extras,
            allow_reason=allow or ALLOWLIST.get(mnemonic),
            example=_FORMATTER.format(instr),
            first_ip=instr.ip,
            region=region,
            sample_ips=[instr.ip],
        )
    stats.instructions += count
    stats.invalid += invalid
    return stats
