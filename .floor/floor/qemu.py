"""Dynamic CPU-floor check under QEMU user mode (PRD F3).

Every CPU model gets a positive control (an instruction at the model's level, must pass)
and a negative control (one level higher, must fail). If a control gives the wrong
result, the runs on that model are inconclusive (F3.2).
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import tempfile
from pathlib import Path

from .controls import control_elf

# QEMU CPU model -> the x86-64 level it supports. QEMU TCG has no AVX-512, so no v4 model.
CPU_MODELS = {
    "qemu64": 1,       # SSE2 only: older and budget CPUs without SSE4.2
    "Nehalem": 2,      # 2008: SSE4.2 and POPCNT, no AVX
    "SandyBridge": 2,  # 2011: AVX but no AVX2, FMA or BMI
    "EPYC-Milan": 3,   # Zen 3 (2021): AVX2, no AVX-512 (the CPU in #3814)
}
DEFAULT_MODELS = tuple(CPU_MODELS)
_VARIANT_RE = re.compile(r"libggml-cpu-([A-Za-z0-9_]+)\.so")


def qemu_binary() -> str | None:
    return shutil.which("qemu-x86_64") or shutil.which("qemu-x86_64-static")


def normalise(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split())


def loaded_variant(log: str) -> str | None:
    """Reads the ggml CPU variant that the backend loader chose, from its log lines."""
    for line in log.splitlines():
        if "load" in line.lower() and "cpu" in line.lower():
            match = _VARIANT_RE.search(line)
            if match:
                return match.group(1)
    return None


def relink_sysroot(root: str | os.PathLike) -> int:
    """Rewrites every absolute symbolic link below ``root`` as a relative link inside ``root``.

    qemu -L looks for an absolute path in the sysroot first, but the host follows an absolute
    link target on the host. An extracted image has /lib64/ld-linux-x86-64.so.2 ->
    /lib/x86_64-linux-gnu/ld-linux-x86-64.so.2, so without this step the host's loader would
    start the image's libraries. Returns the number of links rewritten.
    """
    root = Path(root).resolve()
    count = 0
    for folder, dirs, files in os.walk(root):  # does not enter linked folders
        for name in dirs + files:
            link = Path(folder) / name
            if not link.is_symlink():
                continue
            target = os.readlink(link)
            if not target.startswith("/"):
                continue
            link.unlink()
            link.symlink_to(os.path.relpath(root / target.lstrip("/"), link.parent))
            count += 1
    return count


def _signal_name(number: int) -> str:
    try:
        return signal.Signals(number).name
    except ValueError:
        return f"SIG{number}"


def run(cmd: list[str], cpu: str, *, sysroot: str | None = None, timeout: float = 900,
        env: dict | None = None, qemu: str | None = None) -> dict:
    """Runs ``cmd`` under qemu-x86_64 with one CPU model and records how it ended."""
    qemu = qemu or qemu_binary()
    if qemu is None:
        raise FileNotFoundError("qemu-x86_64 is not installed")
    full = [qemu, "-cpu", cpu] + (["-L", sysroot] if sysroot else []) + cmd
    try:
        proc = subprocess.run(full, capture_output=True, text=True, errors="replace", timeout=timeout,
                              env={**os.environ, **(env or {})})
    except subprocess.TimeoutExpired:
        return {"cpu": cpu, "exit": None, "signal": None, "timeout": True, "stdout": "", "stderr": ""}
    sig = None
    if proc.returncode < 0:
        sig = _signal_name(-proc.returncode)
    elif proc.returncode in (128 + 4, 128 + 6, 128 + 11):  # a shell reports SIGILL, SIGABRT, SIGSEGV this way
        sig = _signal_name(proc.returncode - 128)
    return {"cpu": cpu, "exit": proc.returncode, "signal": sig, "timeout": False,
            "stdout": proc.stdout, "stderr": proc.stderr}


def judge(result: dict, expect: str | None = None) -> str:
    """pass or fail. SIGILL, any other signal, a non-zero exit, a timeout or wrong text fail."""
    if result["timeout"] or result["signal"] or result["exit"] != 0:
        return "fail"
    if expect and normalise(expect) not in normalise(result["stdout"]):
        return "fail"
    return "pass"


def controls(cpu: str, workdir: Path, qemu: str | None = None) -> dict:
    """Runs the positive and the negative control on one CPU model."""
    level = CPU_MODELS[cpu]
    found = {}
    for kind, control_level in (("positive", level), ("negative", level + 1)):
        path = workdir / f"control-v{control_level}"
        if not path.exists():
            path.write_bytes(control_elf(control_level))
            path.chmod(0o755)
        result = run([str(path)], cpu, timeout=60, qemu=qemu)
        verdict = judge(result)
        found[kind] = {"level": control_level, "result": verdict, "signal": result["signal"],
                       "ok": verdict == ("pass" if kind == "positive" else "fail")}
    return found


def _tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.splitlines()[-lines:])


def probe(cmd: list[str], models: tuple[str, ...] = DEFAULT_MODELS, *, expect: str | None = None,
          sysroot: str | None = None, timeout: float = 900, env: dict | None = None) -> dict:
    """Runs ``cmd`` on every CPU model, with the controls. Returns one entry per model.

    With ``sysroot`` (an extracted image), absolute links in it are made relative first (relink_sysroot).
    """
    qemu = qemu_binary()
    if qemu is None:
        raise FileNotFoundError("qemu-x86_64 is not installed")
    relinked = relink_sysroot(sysroot) if sysroot else None
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for cpu in models:
            ctl = controls(cpu, Path(tmp), qemu)
            result = run(cmd, cpu, sysroot=sysroot, timeout=timeout, env=env, qemu=qemu)
            verdict = judge(result, expect)
            valid = all(c["ok"] for c in ctl.values())
            rows.append({
                "cpu": cpu,
                "cpu_level": f"x86-64-v{CPU_MODELS[cpu]}",
                "result": verdict if valid else "inconclusive",
                "raw_result": verdict,
                "exit": result["exit"],
                "signal": result["signal"],
                "timeout": result["timeout"],
                "loaded_variant": loaded_variant(result["stderr"] + "\n" + result["stdout"]),
                "controls": ctl,
                "stdout_tail": _tail(result["stdout"]),
                "stderr_tail": _tail(result["stderr"]),
            })
    return {"command": cmd, "expect": expect, "sysroot": sysroot, "sysroot_links_rewritten": relinked, "runs": rows}
