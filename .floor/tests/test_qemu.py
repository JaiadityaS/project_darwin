"""Tests for the QEMU harness. The runs under QEMU need Linux with qemu-user installed."""

from __future__ import annotations

import pytest

from floor.controls import LEVEL_INSTRUCTION, control_elf
from floor.isa.scan import scan_file
from floor.qemu import CPU_MODELS, controls, judge, loaded_variant, normalise, qemu_binary


@pytest.mark.parametrize("level", sorted(LEVEL_INSTRUCTION))
def test_control_elf_scans_at_its_level(tmp_path, level):
    path = tmp_path / f"control-v{level}"
    path.write_bytes(control_elf(level))
    report = scan_file(path)
    assert report is not None and report.error is None
    assert report.elf_type == "ET_EXEC"
    assert report.level == level


def _result(exit=0, sig=None, stdout="", timeout=False):
    return {"exit": exit, "signal": sig, "stdout": stdout, "timeout": timeout}


def test_judge():
    text = " And so my fellow Americans, ask not what your country can do for you"
    assert judge(_result(stdout=text), "ask not what your country can do for you") == "pass"
    assert judge(_result(stdout="[BLANK_AUDIO]"), "ask not what your country") == "fail"
    assert judge(_result(exit=-4, sig="SIGILL")) == "fail"
    assert judge(_result(exit=1)) == "fail"
    assert judge(_result(exit=None, timeout=True)) == "fail"
    assert judge(_result()) == "pass"


def test_normalise():
    assert normalise("  Ask NOT, what your-country...") == "ask not what your country"


def test_loaded_variant():
    log = "load_backend: loaded CPU backend from /app/build/bin/libggml-cpu-sandybridge.so\n"
    assert loaded_variant(log) == "sandybridge"
    assert loaded_variant("whisper_init_from_file_with_params_no_state: loading model") is None


def test_cpu_models_have_levels():
    assert CPU_MODELS == {"qemu64": 1, "Nehalem": 2, "SandyBridge": 2, "EPYC-Milan": 3}


@pytest.mark.skipif(qemu_binary() is None, reason="qemu-x86_64 is not installed")
@pytest.mark.parametrize("cpu", sorted(CPU_MODELS))
def test_controls_under_qemu(tmp_path, cpu):
    found = controls(cpu, tmp_path)
    assert found["positive"]["result"] == "pass"
    assert found["negative"]["result"] == "fail"
    assert found["negative"]["signal"] == "SIGILL"
