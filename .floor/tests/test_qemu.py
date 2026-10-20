"""Tests for the QEMU harness. The runs under QEMU need Linux with qemu-user installed."""

from __future__ import annotations

import os

import pytest

from floor.controls import LEVEL_INSTRUCTION, control_elf
from floor.isa.scan import scan_file
from floor.qemu import CPU_MODELS, controls, judge, loaded_variant, normalise, qemu_binary, relink_sysroot


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


@pytest.mark.skipif(os.name != "posix", reason="POSIX symbolic links (the sysroot is a Linux image)")
def test_relink_sysroot(tmp_path):
    root = tmp_path / "rootfs"
    (root / "usr/lib/x86_64-linux-gnu").mkdir(parents=True)
    (root / "usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2").write_text("image loader", encoding="utf-8")
    (root / "lib").symlink_to("usr/lib")  # relative: kept as it is
    (root / "lib64").mkdir()
    (root / "lib64/ld-linux-x86-64.so.2").symlink_to("/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2")
    (root / "etc").mkdir()
    (root / "etc/missing").symlink_to("/no/such/file")
    assert relink_sysroot(root) == 2
    loader = root / "lib64/ld-linux-x86-64.so.2"
    assert os.readlink(loader) == os.path.join("..", "lib", "x86_64-linux-gnu", "ld-linux-x86-64.so.2")
    assert loader.read_text(encoding="utf-8") == "image loader"  # the image's file, not the host's
    assert os.readlink(root / "lib") == "usr/lib"
    assert os.readlink(root / "etc/missing") == os.path.join("..", "no", "such", "file")
    assert relink_sysroot(root) == 0


def test_cpu_models_have_levels():
    assert CPU_MODELS == {"qemu64": 1, "Nehalem": 2, "SandyBridge": 2, "EPYC-Milan": 3}


@pytest.mark.skipif(qemu_binary() is None, reason="qemu-x86_64 is not installed")
@pytest.mark.parametrize("cpu", sorted(CPU_MODELS))
def test_controls_under_qemu(tmp_path, cpu):
    found = controls(cpu, tmp_path)
    assert found["positive"]["result"] == "pass"
    assert found["negative"]["result"] == "fail"
    assert found["negative"]["signal"] == "SIGILL"


def test_probe_ci_job():
    """MR pipeline 2961002610: one thread per runner vCPU, and the run limit fits in the job limit."""
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parents[2]
    job = yaml.safe_load((root / ".gitlab-ci.yml").read_text(encoding="utf-8"))["probe"]
    script = job["script"][-1]
    # D-027: a smaller audio context that still holds the 11 s sample (1500 frames = 30 s).
    assert "-f /app/samples/jfk.wav -ac 768 -t 2 -nt" in script and "--timeout 2700" in script
    assert 768 * 30 / 1500 > 11.0
    assert int(job["timeout"].rstrip("m")) * 60 > 2700 + 300  # room for the model, the export and the controls


def test_tools_tag_is_the_recipe_hash():
    """check.sh: TOOLS_TAG is the first 12 hex digits of the SHA-256 of the tools recipe.

    A change to a comment in the recipe changes the tag too (main pipeline 2969295146)."""
    import hashlib
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parents[2]
    tag = yaml.safe_load((root / ".gitlab-ci.yml").read_text(encoding="utf-8"))["variables"]["TOOLS_TAG"]
    assert tag == hashlib.sha256((root / ".gitlab" / "ci" / "tools.Dockerfile").read_bytes()).hexdigest()[:12]


def test_timeout_keeps_partial_output(monkeypatch):
    """MR pipeline 2961093570: a timed-out run had no output; now it keeps what the run printed."""
    import subprocess

    from floor import qemu

    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(a[0], 1, output=b"partial out", stderr=b"load_backend: loaded CPU backend")
    monkeypatch.setattr(qemu.subprocess, "run", fake_run)
    result = qemu.run(["whisper-cli"], "EPYC-Milan", qemu="/usr/bin/qemu-x86_64", timeout=1)
    assert result["timeout"] and result["stdout"] == "partial out"
    assert result["stderr"] == "load_backend: loaded CPU backend" and isinstance(result["seconds"], float)
    assert qemu._text(None) == "" and qemu._text("x") == "x"
