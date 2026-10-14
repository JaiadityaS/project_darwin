"""Builds minimal x86-64 ELF files for the tests."""

from __future__ import annotations

import struct

EHDR_SIZE = 64
PHDR_SIZE = 56
SHDR_SIZE = 64
_EHDR = "<HHIQQQIHHHHHH"
_SHDR = "<IIQQQQIIQQ"


def build_elf(code: bytes, *, base: int = 0x1000, e_type: int = 3, machine: int = 0x3E,
              with_sections: bool = True, symbols: list[tuple[str, int, int]] | None = None) -> bytes:
    """Returns a little-endian ELF64 file whose only code is ``code``.

    e_type: 1 is ET_REL, 2 is ET_EXEC, 3 is ET_DYN. machine: 0x3E is x86-64.
    With ``with_sections=False`` the file has no section headers, only one PT_LOAD
    segment with the X flag (like a stripped file).
    ``symbols`` adds a .symtab with one function per (name, offset in code, size).
    """
    ident = b"ELF" + bytes([2, 1, 1, 0]) + bytes(8)
    if with_sections:
        names = [".text", ".shstrtab"] + ([".symtab", ".strtab"] if symbols else [])
        shstrtab = b"\0" + b"".join(n.encode() + b"\0" for n in names)
        name_off = {n: shstrtab.index(n.encode() + b"\0") for n in names}
        blobs = [code, shstrtab]
        if symbols:
            strtab = b"\0" + b"".join(n.encode() + b"\0" for n, _, _ in symbols)
            symtab = bytes(24) + b"".join(
                struct.pack("<IBBHQQ", strtab.index(n.encode() + b"\0"), 0x12, 0, 1, base + off, size)
                for n, off, size in symbols)
            blobs += [symtab, strtab]
        offsets, pos = [], EHDR_SIZE
        for blob in blobs:
            pos = (pos + 7) & ~7
            offsets.append(pos)
            pos += len(blob)
        sh_off = (pos + 7) & ~7
        header = ident + struct.pack(_EHDR, e_type, machine, 1, base, 0, sh_off, 0,
                                     EHDR_SIZE, PHDR_SIZE, 0, SHDR_SIZE, len(names) + 1, 2)
        shdrs = [struct.pack(_SHDR, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
                 struct.pack(_SHDR, name_off[".text"], 1, 6, base, offsets[0], len(code), 0, 0, 16, 0),
                 struct.pack(_SHDR, name_off[".shstrtab"], 3, 0, 0, offsets[1], len(shstrtab), 0, 0, 1, 0)]
        if symbols:
            shdrs += [struct.pack(_SHDR, name_off[".symtab"], 2, 0, 0, offsets[2], len(blobs[2]), 4, 1, 8, 24),
                      struct.pack(_SHDR, name_off[".strtab"], 3, 0, 0, offsets[3], len(blobs[3]), 0, 0, 1, 0)]
        body = header
        for off, blob in zip(offsets, blobs):
            body += bytes(off - len(body)) + blob
        return body + bytes(sh_off - len(body)) + b"".join(shdrs)
    code_off = EHDR_SIZE + PHDR_SIZE
    header = ident + struct.pack(_EHDR, e_type, machine, 1, base, EHDR_SIZE, 0, 0,
                                 EHDR_SIZE, PHDR_SIZE, 1, SHDR_SIZE, 0, 0)
    phdr = struct.pack("<IIQQQQQQ", 1, 5, code_off, base, base, len(code), len(code), 0x1000)
    return header + phdr + code
