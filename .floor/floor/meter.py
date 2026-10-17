"""Whole-machine CPU and memory use of one release check (PRD F14.1: the R2 input of SCI).

`floor meter start` writes a state file and starts a sampler process. Every few seconds the sampler
adds the used memory to a GB-seconds total (trapezoid rule). `floor meter stop` stops the sampler,
adds the last interval and gives the totals that `footprint.release_inputs` reads.

Linux only: the busy CPU time comes from /proc/stat and the used memory from /proc/meminfo. The meter
counts the whole machine, so use it on a runner VM that runs one job, not on a shared host.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROC_STAT = "/proc/stat"
PROC_MEMINFO = "/proc/meminfo"
PROC_CPUINFO = "/proc/cpuinfo"
BUSY_FIELDS = (0, 1, 2, 5, 6)  # user, nice, system, irq and softirq, after the "cpu" label
MAX_S = 6 * 3600  # a sampler that nobody stops ends after this time (the GitHub job limit)


def busy_ticks(stat: str) -> int:
    """The busy CPU ticks of all CPUs, from the first line of /proc/stat."""
    label, *values = stat.split("\n", 1)[0].split()
    if label != "cpu":
        raise ValueError(f"not a /proc/stat text: the first field is {label!r}")
    return sum(int(values[i]) for i in BUSY_FIELDS)


def memory_used_gb(meminfo: str) -> float:
    """MemTotal minus MemAvailable (/proc/meminfo gives kB), in GB."""
    kb = {}
    for line in meminfo.splitlines():
        key, _, value = line.partition(":")
        if value.split():
            kb[key] = int(value.split()[0])
    return (kb["MemTotal"] - kb["MemAvailable"]) / 1048576


def cpu_model(cpuinfo: str) -> str | None:
    """The first "model name" in /proc/cpuinfo."""
    for line in cpuinfo.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "model name":
            return value.strip()
    return None


def add(acc: dict, t: float, gb: float) -> dict:
    """Add the interval from the last sample to the sample (t, gb), with the trapezoid rule."""
    return {"t": t, "gb": gb, "gb_s": acc["gb_s"] + (acc["gb"] + gb) / 2 * (t - acc["t"]),
            "peak_gb": max(acc["peak_gb"], gb), "count": acc["count"] + 1}


def totals(state: dict, acc: dict, t: float, busy: int) -> dict:
    """The fields that `footprint.release_inputs` reads, plus the vCPU-seconds and the memory peak."""
    wall = t - state["t0"]
    return {"measured_at": state["started_at"], "wall_s": round(wall, 3),
            "cpu_s": round((busy - state["busy_ticks"]) / state["clk_tck"], 3), "vcpus": state["vcpus"],
            "vcpu_s": round(wall * state["vcpus"], 3), "memory_gb_s": round(acc["gb_s"], 3),
            "memory_peak_gb": round(acc["peak_gb"], 3), "cpu_model": state["cpu_model"],
            "samples": acc["count"], "interval_s": state["interval_s"]}


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def samples_path(state: Path) -> Path:
    return state.with_name(state.name + ".samples.json")


def _write_atomic(path: Path, doc: dict) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _is_sampler(pid: int, state: Path) -> bool:
    """True when ``pid`` runs `floor meter sample` for this state file. A reused PID or a zombie is not."""
    try:
        args = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except OSError:
        return False
    return b"sample" in args and os.fsencode(str(state.resolve())) in args


def _end(pid: int | None, state: Path, timeout: float = 10.0) -> None:
    if not pid or not _is_sampler(pid, state):
        return
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(int(timeout / 0.05)):
            if not _is_sampler(pid, state):
                return
            time.sleep(0.05)
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def start(state: Path, interval: float = 5.0) -> dict:
    """Write the state file and start the sampler in a new session, so that it outlives this process."""
    if state.exists():
        old = json.loads(state.read_text(encoding="utf-8")).get("pid")
        if old and _is_sampler(old, state):
            raise RuntimeError(f"a sampler (PID {old}) already runs for {state}")
    state.parent.mkdir(parents=True, exist_ok=True)
    t0, gb = time.monotonic(), memory_used_gb(_read(PROC_MEMINFO))
    doc = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "t0": t0,
           "busy_ticks": busy_ticks(_read(PROC_STAT)), "clk_tck": os.sysconf("SC_CLK_TCK"), "vcpus": os.cpu_count(),
           "cpu_model": cpu_model(_read(PROC_CPUINFO)), "interval_s": interval}
    _write_atomic(samples_path(state), {"t": t0, "gb": gb, "gb_s": 0.0, "peak_gb": gb, "count": 1})
    proc = subprocess.Popen([sys.executable, "-m", "floor", "meter", "sample", "--state", str(state.resolve()),
                             "--interval", str(interval)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    doc["pid"] = proc.pid
    _write_atomic(state, doc)
    return doc


def sample(state: Path, interval: float, max_s: float = MAX_S) -> None:
    """The sampler loop. SIGTERM ends it at any time: each write replaces the whole samples file."""
    path = samples_path(state)
    acc = json.loads(path.read_text(encoding="utf-8"))
    end = acc["t"] + max_s
    while time.monotonic() < end:
        time.sleep(interval)
        gb = memory_used_gb(_read(PROC_MEMINFO))
        acc = add(acc, time.monotonic(), gb)
        _write_atomic(path, acc)


def stop(state: Path) -> dict:
    """Stop the sampler, add the last interval and give the totals."""
    doc = json.loads(state.read_text(encoding="utf-8"))
    _end(doc.get("pid"), state)
    busy, gb, t = busy_ticks(_read(PROC_STAT)), memory_used_gb(_read(PROC_MEMINFO)), time.monotonic()
    acc = add(json.loads(samples_path(state).read_text(encoding="utf-8")), t, gb)
    return totals(doc, acc, t, busy)
