"""Control programs for the QEMU runs (PRD F3.2).

Each control is a tiny static x86-64 executable: one instruction of a given level,
then exit(0). On a CPU model at or above that level it exits with 0. On a lower CPU
model it dies with SIGILL. The files are made here, so no compiler is needed.
"""

from __future__ import annotations

import struct

BASE = 0x400000
_EHDR = "<4s5B7xHHIQQQIHHHHHH"
_PHDR = "<IIQQQQQQ"
_SHDR = "<IIQQQQIIQQ"
_HEADERS = 64 + 56
_EXIT0 = bytes.fromhex("b83c000000" "31ff" "0f05")  # mov eax, 60; xor edi, edi; syscall

# One instruction per level. v3 uses an AVX2 form, so SandyBridge (AVX but no AVX2) fails it.
LEVEL_INSTRUCTION = {
    1: ("addps xmm0, xmm1", bytes.fromhex("0f58c1")),
    2: ("popcnt rax, rcx", bytes.fromhex("f3480fb8c1")),
    3: ("vpaddd ymm0, ymm1, ymm2", bytes.fromhex("c5f5fec2")),
    4: ("vpaddd zmm0, zmm1, zmm2", bytes.fromhex("62f17548fec2")),
}


def control_elf(level: int) -> bytes:
    """Returns a static ET_EXEC file that runs one level-``level`` instruction and exits 0.

    One PT_LOAD (read + execute) maps the whole file at BASE. The file also has a `.text`
    section header, so that the static scanner decodes only the code.
    """
    code = LEVEL_INSTRUCTION[level][1] + _EXIT0
    shstrtab = b"\0.text\0.shstrtab\0"
    str_off = _HEADERS + len(code)
    sh_off = (str_off + len(shstrtab) + 7) & ~7
    size = sh_off + 3 * 64
    header = struct.pack(_EHDR, b"\x7fELF", 2, 1, 1, 0, 0, 2, 0x3E, 1, BASE + _HEADERS, 64, sh_off, 0,
                         64, 56, 1, 64, 3, 2)
    phdr = struct.pack(_PHDR, 1, 5, 0, BASE, BASE, size, size, 0x1000)
    sections = b"".join([
        struct.pack(_SHDR, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        struct.pack(_SHDR, 1, 1, 6, BASE + _HEADERS, _HEADERS, len(code), 0, 0, 1, 0),
        struct.pack(_SHDR, 7, 3, 0, 0, str_off, len(shstrtab), 0, 0, 1, 0),
    ])
    body = header + phdr + code + shstrtab
    return body + bytes(sh_off - len(body)) + sections
