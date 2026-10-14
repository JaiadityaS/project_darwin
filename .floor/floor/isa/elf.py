"""ELF helpers: executable regions and the GNU x86 ISA-level note."""

from __future__ import annotations

import struct

SHF_EXECINSTR = 0x4
PF_X = 0x1
NT_GNU_PROPERTY_TYPE_0 = 5
GNU_PROPERTY_X86_ISA_1_NEEDED = 0xC0008002
_ISA_BITS = ((0x1, "x86-64-v1"), (0x2, "x86-64-v2"), (0x4, "x86-64-v3"), (0x8, "x86-64-v4"))


def exec_regions(elf) -> list[tuple[str, int, bytes]]:
    """Returns (name, address, bytes) for every executable region.

    Uses the section headers when they exist, else PT_LOAD segments with the X flag.
    """
    regions = []
    for section in elf.iter_sections():
        if section["sh_type"] == "SHT_PROGBITS" and section["sh_flags"] & SHF_EXECINSTR and section["sh_size"]:
            regions.append((section.name, section["sh_addr"], section.data()))
    if regions:
        return regions
    for index, segment in enumerate(elf.iter_segments()):
        if segment["p_type"] == "PT_LOAD" and segment["p_flags"] & PF_X and segment["p_filesz"]:
            regions.append((f"LOAD{index}", segment["p_vaddr"], segment.data()))
    return regions


def isa_needed(elf) -> list[str] | None:
    """Reads GNU_PROPERTY_X86_ISA_1_NEEDED from .note.gnu.property, if the file has it."""
    section = elf.get_section_by_name(".note.gnu.property")
    if section is None:
        return None
    data = section.data()
    found = set()
    offset = 0
    while offset + 12 <= len(data):
        namesz, descsz, note_type = struct.unpack_from("<III", data, offset)
        offset += 12
        name = data[offset:offset + namesz]
        offset += (namesz + 3) & ~3
        desc = data[offset:offset + descsz]
        offset += (descsz + 7) & ~7
        if note_type != NT_GNU_PROPERTY_TYPE_0 or not name.startswith(b"GNU"):
            continue
        pos = 0
        while pos + 8 <= len(desc):
            pr_type, pr_datasz = struct.unpack_from("<II", desc, pos)
            pos += 8
            value = desc[pos:pos + pr_datasz]
            pos += (pr_datasz + 7) & ~7
            if pr_type == GNU_PROPERTY_X86_ISA_1_NEEDED and len(value) >= 4:
                bits = struct.unpack_from("<I", value)[0]
                found.update(name for bit, name in _ISA_BITS if bits & bit)
    return sorted(found) or None
