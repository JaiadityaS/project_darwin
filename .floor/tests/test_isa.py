"""Tests for the static CPU-floor scanner (F2, AC-F2 on synthetic files)."""

from __future__ import annotations

import json

import pytest
from elfbuild import build_elf
from iced_x86 import CpuidFeature, Mnemonic

from floor.cli import main
from floor.isa.allowlist import ALLOWLIST, GUARDED, base_name, guarded_reason
from floor.isa.decode import FEATURE_NAMES, decode_region
from floor.isa.levels import FEATURE_LEVEL, classify, level_name, parse_level
from floor.isa.scan import FileReport, classify_role, scan_file, scan_path, summarize

# name: (machine code as hex, mnemonic, level, extras, allowlisted)
SNIPPETS = {
    "addps": ("0f58c1", "ADDPS", 1, (), False),
    "popcnt": ("f30fb8c1", "POPCNT", 2, (), False),
    "andn": ("c4e260f2c1", "ANDN", 3, (), False),
    "vfmadd231ps": ("c4e275b8c2", "VFMADD231PS", 3, (), False),
    "vpaddd_zmm": ("62f17548fec2", "VPADDD", 4, (), False),
    "vpaddd_ymm_evex": ("62f17528fec2", "VPADDD", 4, (), False),
    "aesenc": ("660f38dcc1", "AESENC", 1, ("AES",), False),
    "vpdpbusd_vex": ("c4e27550c2", "VPDPBUSD", 3, ("AVX_VNNI",), False),
    "tzcnt": ("f30fbcc1", "TZCNT", 3, (), True),
    "endbr64": ("f30f1efa", "ENDBR64", 1, ("CET_IBT",), True),
    "endbr32": ("f30f1efb", "ENDBR32", 1, ("CET_IBT",), True),
    "rdsspq": ("f3480f1ec8", "RDSSPQ", 1, ("CET_SS",), True),
    "rdsspd": ("f30f1ec8", "RDSSPD", 1, ("CET_SS",), True),
    "xgetbv": ("0f01d0", "XGETBV", 3, (), True),
}
RET = b"\xc3"


@pytest.mark.parametrize("name", sorted(SNIPPETS))
def test_snippet_classification(name):
    hexcode, mnemonic, level, extras, allowlisted = SNIPPETS[name]
    stats = decode_region(bytes.fromhex(hexcode), 0x1000, ".text")
    assert (stats.instructions, stats.invalid) == (1, 0)
    (stat,) = stats.opcodes.values()
    assert stat.mnemonic == mnemonic
    assert (stat.level, stat.extras) == (level, extras)
    assert (stat.allow_reason is not None) == allowlisted


def test_level_features_are_iced_names():
    for name in FEATURE_LEVEL:
        assert hasattr(CpuidFeature, name), name
        assert FEATURE_NAMES[getattr(CpuidFeature, name)] == name


def test_allowlist_entries_are_real_mnemonics_with_reasons():
    for mnemonic, reason in ALLOWLIST.items():
        assert hasattr(Mnemonic, mnemonic), mnemonic
        assert len(reason) > 20


def test_every_allowlist_entry_has_a_snippet():
    assert {s[1] for s in SNIPPETS.values() if s[4]} == set(ALLOWLIST)


@pytest.mark.parametrize("text,level", [("x86-64-v3", 3), ("v2", 2), ("4", 4), (" X86-64-V1 ", 1)])
def test_parse_level(text, level):
    assert parse_level(text) == level
    assert parse_level(level_name(level)) == level


@pytest.mark.parametrize("text", ["v5", "v0", "haswell"])
def test_parse_level_rejects_unknown(text):
    with pytest.raises(ValueError):
        parse_level(text)


@pytest.mark.parametrize("features,expected", [
    (("AVX2",), (3, ())),
    (("AVX512VL", "AVX512_VNNI"), (4, ("AVX512_VNNI",))),
    (("AES",), (1, ("AES",))),
    (("AVX_VNNI",), (3, ("AVX_VNNI",))),
    ((), (1, ())),
])
def test_classify(features, expected):
    assert classify(features) == expected


def test_scan_file_reports_level_extras_and_allowlist(tmp_path):
    path = tmp_path / "libmix.so"
    path.write_bytes(build_elf(b"".join(bytes.fromhex(s[0]) for s in SNIPPETS.values()) + RET))
    report = scan_file(path)
    assert report is not None and report.error is None
    assert (report.instructions, report.invalid) == (len(SNIPPETS) + 1, 0)
    assert report.level == 4
    assert report.extras == {"AES": 1, "AVX_VNNI": 1}
    assert set(report.allowlisted) == set(ALLOWLIST)
    assert report.evidence[0]["level"] == "x86-64-v4"
    assert {"AES", "AVX_VNNI"} <= {f for e in report.evidence for f in e["features"]}
    assert report.to_dict()["level"] == "x86-64-v4"


def test_allowlisted_opcodes_do_not_raise_the_level(tmp_path):
    allowed = b"".join(bytes.fromhex(s[0]) for s in SNIPPETS.values() if s[4])
    path = tmp_path / "libcet.so"
    path.write_bytes(build_elf(allowed + bytes.fromhex("0f58c1") + RET))
    report = scan_file(path)
    assert report.level == 1
    assert report.extras == {}
    assert report.evidence == []


def test_scan_file_without_section_headers_uses_load_segments(tmp_path):
    path = tmp_path / "stripped"
    path.write_bytes(build_elf(bytes.fromhex("f30fb8c1") + RET, e_type=2, with_sections=False))
    report = scan_file(path)
    assert report.elf_type == "ET_EXEC"
    assert report.level == 2
    assert report.evidence[0]["region"] == "LOAD0"


def test_scan_path_skips_non_elf_relocatable_and_foreign_files(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "obj.o").write_bytes(build_elf(RET, e_type=1))
    (tmp_path / "arm64.so").write_bytes(build_elf(RET, machine=0xB7))
    assert scan_path(tmp_path) == []


def test_scan_path_reports_damaged_elf_as_error(tmp_path):
    (tmp_path / "broken.so").write_bytes(build_elf(RET)[:40])
    (report,) = scan_path(tmp_path)
    assert report.error
    assert summarize([report])["files"]["errors"] == ["broken.so"]


@pytest.mark.parametrize("path,expected", [
    ("build/bin/whisper-cli", ("core", None)),
    ("app/build/ggml/src/libggml-cpu.so", ("core", None)),
    ("app/build/bin/libggml-cpu-haswell.so", ("variant", "haswell")),
    ("lib/libggml-cpu-x64.so.0", ("variant", "x64")),
    ("app/build/CMakeFiles/3.28.3/CompilerIdC/a.out", ("build-tool", None)),
])
def test_classify_role(path, expected):
    assert classify_role(path) == expected


def _report(path, level, extras=None, role=None):
    file_role, variant = classify_role(path)
    return FileReport(path=path, sha256="0" * 64, size=1, elf_type="ET_DYN", role=role or file_role,
                      variant=variant, level=level, extras=extras or {})


def test_summarize_all_variants_build():
    summary = summarize([
        _report("build/bin/whisper-cli", 1),
        _report("build/bin/libggml-base.so", 1),
        _report("build/bin/libggml-cpu-x64.so", 1),
        _report("build/bin/libggml-cpu-haswell.so", 3),
        _report("build/bin/libggml-cpu-icelake.so", 4, {"AVX512_VNNI": 40}),
    ])
    assert summary["floor"] == {"level": "x86-64-v1", "extras": [], "sources": []}
    assert summary["baseline_variant"] == "x64"
    assert summary["variants"] == {"haswell": "x86-64-v3", "icelake": "x86-64-v4", "x64": "x86-64-v1"}
    assert summary["highest_level_found"] == "x86-64-v4"


def test_summarize_native_build():
    summary = summarize([
        _report("build/bin/whisper-cli", 1),
        _report("build/ggml/src/libggml-cpu.so", 4, {"AVX512_VNNI": 12}),
    ])
    assert summary["floor"] == {"level": "x86-64-v4", "extras": ["AVX512_VNNI"],
                                "sources": ["build/ggml/src/libggml-cpu.so"]}
    assert summary["baseline_variant"] is None


def test_summarize_ignores_build_tools_and_distro_libraries():
    summary = summarize([
        _report("build/bin/whisper-cli", 1),
        _report("build/CMakeFiles/3.22.1/CompilerIdC/a.out", 4),
        _report("usr/lib/x86_64-linux-gnu/libc.so.6", 4, {"AVX512_VBMI2": 3}, role="distro"),
    ])
    assert summary["floor"]["level"] == "x86-64-v1"
    assert summary["floor"]["extras"] == []
    assert summary["highest_level_found"] == "x86-64-v1"
    assert summary["files"]["build-tool"] == 1 and summary["files"]["distro"] == 1


def test_cli_scan_writes_json(tmp_path, capsys):
    root = tmp_path / "app"
    (root / "bin").mkdir(parents=True)
    (root / "bin" / "whisper-cli").write_bytes(build_elf(bytes.fromhex("0f58c1") + RET))
    (root / "bin" / "libggml-cpu-x64.so").write_bytes(build_elf(bytes.fromhex("0f58c1") + RET))
    (root / "bin" / "libggml-cpu-haswell.so").write_bytes(build_elf(bytes.fromhex("c4e275b8c2") + RET))
    out = tmp_path / "out" / "scan.json"
    assert main(["scan", str(root), "--json", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["summary"]["floor"]["level"] == "x86-64-v1"
    assert doc["summary"]["baseline_variant"] == "x64"
    assert doc["summary"]["highest_level_found"] == "x86-64-v3"
    assert len(doc["files"]) == 3
    assert "Floor: x86-64-v1" in capsys.readouterr().out


def test_cli_scan_without_elf_files_returns_2(tmp_path):
    assert main(["scan", str(tmp_path)]) == 2
    assert main(["scan", str(tmp_path / "missing")]) == 2


LZCNT = bytes.fromhex("f30fbdc1")


def test_guarded_entries_are_real_mnemonics_with_reasons():
    for mnemonic, entries in GUARDED.items():
        assert hasattr(Mnemonic, mnemonic)
        assert entries and all(len(reason) > 40 for _, reason in entries)
    assert guarded_reason("LZCNT", "drflac__seek_past_next_set_bit")
    assert guarded_reason("LZCNT", "_ZL29ma_dr_flac__decode_flac_frameP10ma_dr_flac")
    assert guarded_reason("LZCNT", "_ZL9whisper_xP10ma_dr_flac") is None
    assert base_name("_ZL27ma_dr_flac__seek_flac_frameP10ma_dr_flac") == "ma_dr_flac__seek_flac_frame"
    assert guarded_reason("LZCNT", "whisper_full") is None
    assert guarded_reason("LZCNT", None) is None
    assert guarded_reason("ANDN", "drflac__seek_past_next_set_bit") is None


def test_lzcnt_inside_a_guarded_function_does_not_raise_the_level(tmp_path):
    code = LZCNT + RET + bytes.fromhex("0f58c1") + RET
    path = tmp_path / "whisper-cli"
    path.write_bytes(build_elf(code, e_type=2, symbols=[("_ZL27ma_dr_flac__seek_flac_frameP10ma_dr_flac", 0, 5), ("main", 5, 4)]))
    report = scan_file(path)
    assert report.error is None
    assert report.level == 1
    assert report.allowlisted == {"LZCNT": 1}


def test_lzcnt_outside_a_guarded_function_raises_the_level_and_names_it(tmp_path):
    code = LZCNT + RET + LZCNT + RET
    path = tmp_path / "libwhisper.so"
    path.write_bytes(build_elf(code, symbols=[("drflac__clz", 0, 5), ("whisper_encode", 5, 5)]))
    report = scan_file(path)
    assert report.level == 3
    assert report.allowlisted == {"LZCNT": 1}
    assert report.evidence[0]["mnemonic"] == "LZCNT"
    assert report.evidence[0]["count"] == 1
    assert report.evidence[0]["functions"] == ["whisper_encode"]


def test_lzcnt_without_symbols_counts(tmp_path):
    path = tmp_path / "stripped"
    path.write_bytes(build_elf(LZCNT + RET, e_type=2))
    report = scan_file(path)
    assert report.level == 3
    assert report.evidence[0]["functions"] == []
