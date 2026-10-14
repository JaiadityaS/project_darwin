"""Builds minimal x86-64 ELF files for the tests."""

from __future__ import annotations

import struct

EHDR_SIZE = 64
PHDR_SIZE = 56
SHDR_SIZE = 64
_EHDR = "<HHIQQQIHHHHHH"
_SHDR = "<IIQQQQIIQQ"


def build_elf(code: bytes, *, base: int = 0x1000, e_type: int = 3, machine: int = 0x3E,
              with_sections: bool = True) -> bytes:
    """Returns a little-endian ELF64 file whose only code is ``code``.

    e_type: 1 is ET_REL, 2 is ET_EXEC, 3 is ET_DYN. machine: 0x3E is x86-64.
    With ``with_sections=False`` the file has no section headers, only one PT_LOAD
    segment with the X flag (like a stripped file).
    """
    ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8)
    if with_sections:
        shstrtab = b"\0.text\0.shstrtab\0"
        code_off = EHDR_SIZE
        str_off = code_off + len(code)
        sh_off = (str_off + len(shstrtab) + 7) & ~7
        header = ident + struct.pack(_EHDR, e_type, machine, 1, base, 0, sh_off, 0,
                                     EHDR_SIZE, PHDR_SIZE, 0, SHDR_SIZE, 3, 2)
        sections = b"".join([
            struct.pack(_SHDR, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
            struct.pack(_SHDR, 1, 1, 6, base, code_off, len(code), 0, 0, 16, 0),
            struct.pack(_SHDR, 7, 3, 0, 0, str_off, len(shstrtab), 0, 0, 1, 0),
        ])
        body = header + code + shstrtab
        return body + bytes(sh_off - len(body)) + sections
    code_off = EHDR_SIZE + PHDR_SIZE
    header = ident + struct.pack(_EHDR, e_type, machine, 1, base, EHDR_SIZE, 0, 0,
                                 EHDR_SIZE, PHDR_SIZE, 1, SHDR_SIZE, 0, 0)
    phdr = struct.pack("<IIQQQQQQ", 1, 5, code_off, base, base, len(code), len(code), 0x1000)
    return header + phdr + code
