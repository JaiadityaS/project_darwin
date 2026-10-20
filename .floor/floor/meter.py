"""CPU and memory use of one release check (F14.1: the R2 input of SCI).

`floor meter start` writes a state file and starts a sampler process. Every few seconds the sampler
adds the used memory to a GB-seconds total (trapezoid rule). `floor meter stop` stops the sampler,
adds the last interval and gives the totals that `footprint.release_inputs` reads. `floor meter join`
adds the totals of the jobs of one release check (D-015).

Linux only. Two scopes:
- the whole machine: the busy CPU time from /proc/stat, the used memory from /proc/meminfo. Use it on
  a runner VM that runs one job, not on a shared host.
- one cgroup v2 group, for example a job container (`--cgroup`): the CPU time from cpu.stat and the
  working set (memory.current minus the inactive file cache) of the group and its children.
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
CGROUP = "/sys/fs/cgroup"  # in a container with a private cgroup namespace: the container's own group
BUSY_FIELDS = (0, 1, 2, 5, 6)  # user, nice, system, irq and softirq, after the "cpu" label
US_PER_S = 1_000_000  # cpu.stat counts microseconds: in the cgroup scope, the "ticks" are microseconds
MAX_S = 6 * 3600  # a sampler that nobody stops ends after this time (the GitHub job limit)
SUMS = ("wall_s", "cpu_s", "vcpu_s", "memory_gb_s")


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


def _flat(text: str) -> dict[str, int]:
    """A cgroup v2 flat-keyed file ("key value" lines), such as cpu.stat or memory.stat."""
    return {key: int(value) for key, _, value in (line.partition(" ") for line in text.splitlines()) if value}


def cgroup_usage_us(cpu_stat: str) -> int:
    """The CPU time of the group and all its children, in microseconds (usage_usec of cpu.stat)."""
    stats = _flat(cpu_stat)
    if "usage_usec" not in stats:
        raise ValueError("not a cgroup v2 cpu.stat text: no usage_usec")
    return stats["usage_usec"]


def cgroup_memory_gb(current: str, memory_stat: str) -> float:
    """The working set in GB: memory.current minus the inactive file cache (inactive_file of memory.stat).
    The kernel can take back that cache at any time, so it does not count."""
    return max(int(current) - _flat(memory_stat).get("inactive_file", 0), 0) / 2**30


def cgroup_vcpus(cpu_max: str | None, count: int) -> float | int:
    """The CPUs of the group: the quota of cpu.max ("200000 100000" is 2), or ``count`` when there is none."""
    fields = (cpu_max or "max").split()
    if fields[0] == "max":
        return count
    vcpus = int(fields[0]) / int(fields[1])
    return min(int(vcpus) if vcpus.is_integer() else round(vcpus, 3), count)


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
            "scope": "cgroup" if state.get("cgroup") else "machine", "samples": acc["count"],
            "interval_s": state["interval_s"]}


def join(docs: dict[str, dict]) -> dict:
    """One release check from the meters of its jobs, as {job name: `floor meter stop` output}.

    The sums of the times and the GB-seconds, as if the jobs ran one after the other on one runner.
    ``vcpus`` is the mean, weighted by time, so ``vcpus * wall_s`` is still the sum of the vCPU-seconds."""
    if not docs:
        raise ValueError("no meter files to join")
    total = {key: round(sum(doc[key] for doc in docs.values()), 3) for key in SUMS}
    counts = {doc["vcpus"] for doc in docs.values()}
    models = {doc.get("cpu_model") for doc in docs.values()}
    return {"measured_at": min(doc["measured_at"] for doc in docs.values()), "wall_s": total["wall_s"],
            "cpu_s": total["cpu_s"],
            "vcpus": counts.pop() if len(counts) == 1 else round(total["vcpu_s"] / total["wall_s"], 3),
            "vcpu_s": total["vcpu_s"], "memory_gb_s": total["memory_gb_s"],
            "memory_peak_gb": max(doc["memory_peak_gb"] for doc in docs.values()),
            "cpu_model": models.pop() if len(models) == 1 else None,  # None: the jobs ran on more than one CPU model
            "scope": ", ".join(sorted({doc.get("scope", "machine") for doc in docs.values()})),
            "jobs": {name: {key: doc.get(key) for key in ("measured_at", *SUMS, "memory_peak_gb", "cpu_model", "evidence")}
                     for name, doc in sorted(docs.items())}}


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _busy(cgroup: str | None) -> int:
    return cgroup_usage_us(_read(f"{cgroup}/cpu.stat")) if cgroup else busy_ticks(_read(PROC_STAT))


def _memory_gb(cgroup: str | None) -> float:
    if cgroup:
        return cgroup_memory_gb(_read(f"{cgroup}/memory.current"), _read(f"{cgroup}/memory.stat"))
    return memory_used_gb(_read(PROC_MEMINFO))


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


def _vcpus(cgroup: str | None) -> float | int:
    if not cgroup:
        return os.cpu_count()
    cpu_max = Path(cgroup, "cpu.max")  # only in a group with the cpu controller
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else os.cpu_count()
    return cgroup_vcpus(cpu_max.read_text(encoding="utf-8") if cpu_max.exists() else None, cpus)


def start(state: Path, interval: float = 5.0, cgroup: str | None = None) -> dict:
    """Write the state file and start the sampler in a new session, so that it outlives this process.
    With ``cgroup`` (a cgroup v2 folder), the meter counts that group, not the whole machine."""
    if state.exists():
        old = json.loads(state.read_text(encoding="utf-8")).get("pid")
        if old and _is_sampler(old, state):
            raise RuntimeError(f"a sampler (PID {old}) already runs for {state}")
    state.parent.mkdir(parents=True, exist_ok=True)
    cgroup = str(Path(cgroup).resolve()) if cgroup else None
    t0, gb = time.monotonic(), _memory_gb(cgroup)
    doc = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "t0": t0, "cgroup": cgroup,
           "busy_ticks": _busy(cgroup), "clk_tck": US_PER_S if cgroup else os.sysconf("SC_CLK_TCK"),
           "vcpus": _vcpus(cgroup), "cpu_model": cpu_model(_read(PROC_CPUINFO)), "interval_s": interval}
    _write_atomic(samples_path(state), {"t": t0, "gb": gb, "gb_s": 0.0, "peak_gb": gb, "count": 1})
    cmd = [sys.executable, "-m", "floor", "meter", "sample", "--state", str(state.resolve()), "--interval", str(interval)]
    proc = subprocess.Popen(cmd + (["--cgroup", cgroup] if cgroup else []), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    doc["pid"] = proc.pid
    _write_atomic(state, doc)
    return doc


def sample(state: Path, interval: float, max_s: float = MAX_S, cgroup: str | None = None) -> None:
    """The sampler loop. SIGTERM ends it at any time: each write replaces the whole samples file."""
    path = samples_path(state)
    acc = json.loads(path.read_text(encoding="utf-8"))
    end = acc["t"] + max_s
    while time.monotonic() < end:
        time.sleep(interval)
        gb = _memory_gb(cgroup)
        acc = add(acc, time.monotonic(), gb)
        _write_atomic(path, acc)


def stop(state: Path) -> dict:
    """Stop the sampler, add the last interval and give the totals. Then remove the state files, so that
    a second stop (for example in an exit trap) finds no meter."""
    doc = json.loads(state.read_text(encoding="utf-8"))
    _end(doc.get("pid"), state)
    cgroup = doc.get("cgroup")
    busy, gb, t = _busy(cgroup), _memory_gb(cgroup), time.monotonic()
    acc = add(json.loads(samples_path(state).read_text(encoding="utf-8")), t, gb)
    result = totals(doc, acc, t, busy)
    for path in (samples_path(state), state):
        path.unlink(missing_ok=True)
    return result
