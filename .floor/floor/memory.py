"""Memory floor (F7): the smallest cgroup memory limit at which a run still passes, and peak RSS.

Linux only. Each run gets a memory limit and no swap, under /usr/bin/time -v for the peak RSS.
Two ways to set the limit:
- systemd (the default): a transient scope with MemoryMax. In CI the job runs as a user with sudo.
- cgroup v2 directly (``cgroup_root``): for a job container that runs as root with no systemd, for
  example a GitLab.com Kubernetes runner. Each run gets its own child cgroup.
"""

from __future__ import annotations

import errno
import re
import subprocess
import time
from pathlib import Path

DEFAULT_LIMITS_MB = (512, 768, 1024, 1536, 2048, 3072, 4096)
CGROUP_ROOT = Path("/sys/fs/cgroup")
_MAX_RSS = re.compile(r"Maximum resident set size \(kbytes\):\s*(\d+)")
_TAIL = 2000


def wrapper(limit_mb: int, sudo: bool = True) -> list[str]:
    cmd = ["systemd-run", "--scope", "--quiet", "--collect",
           "-p", f"MemoryMax={limit_mb}M", "-p", "MemorySwapMax=0"]
    return (["sudo", "--preserve-env"] if sudo else []) + cmd + ["--", "/usr/bin/time", "-v"]


def cgroup_setup(root: Path = CGROUP_ROOT) -> None:
    """Lets the child cgroups of ``root`` have memory limits. In cgroup v2 a cgroup that has
    processes cannot give a controller to its children, so the processes move to a leaf first."""
    control = root / "cgroup.subtree_control"
    if "memory" in control.read_text(encoding="utf-8").split():
        return
    leaf = root / "floor-job"
    leaf.mkdir(exist_ok=True)
    for pid in (root / "cgroup.procs").read_text(encoding="utf-8").split():
        try:
            (leaf / "cgroup.procs").write_text(pid, encoding="utf-8")  # one PID per write
        except OSError:  # the process has ended
            pass
    control.write_text("+memory", encoding="utf-8")


def cgroup_wrapper(group: Path) -> list[str]:
    """The shell moves itself into ``group`` and then becomes /usr/bin/time, so the command and its
    children run in ``group``."""
    return ["sh", "-c", 'echo $$ > "$0/cgroup.procs" && exec "$@"', str(group), "/usr/bin/time", "-v"]


def _cgroup_remove(group: Path) -> None:
    """Ends what is left in ``group`` (cgroup.kill, Linux 5.14+), for example after a timeout, and removes it."""
    try:
        (group / "cgroup.kill").write_text("1", encoding="utf-8")
    except OSError:
        pass
    for _ in range(50):
        try:
            group.rmdir()
            return
        except OSError as exc:
            if exc.errno != errno.EBUSY:
                return
            time.sleep(0.1)


def peak_rss_mb(stderr: str) -> int | None:
    found = _MAX_RSS.findall(stderr)
    return round(int(found[-1]) / 1024) if found else None


def judge_run(code: int, output: str, expect: str | None) -> str:
    if code in (137, -9) or "Command terminated by signal 9" in output:
        return "oom"
    if code != 0:
        return "fail"
    if expect and expect.lower() not in output.lower():
        return "wrong-output"
    return "pass"


def run(cmd: list[str], limit_mb: int, expect: str | None = None, timeout: float = 900, sudo: bool = True,
        cgroup_root: Path | None = None) -> dict:
    group = None
    if cgroup_root is None:
        prefix = wrapper(limit_mb, sudo)
    else:
        group = cgroup_root / f"floor-{limit_mb}"
        group.mkdir(exist_ok=True)
        (group / "memory.max").write_text(str(limit_mb * 1024 * 1024), encoding="utf-8")
        (group / "memory.swap.max").write_text("0", encoding="utf-8")
        prefix = cgroup_wrapper(group)
    try:
        proc = subprocess.run(prefix + cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        return {"limit_mb": limit_mb, "result": "timeout", "exit": None, "peak_rss_mb": None,
                "stderr_tail": (exc.stderr or b"")[-_TAIL:].decode("utf-8", "replace") if exc.stderr else ""}
    finally:
        if group is not None:
            _cgroup_remove(group)
    # /usr/bin/time reports the child's exit status as its own
    signal = re.search(r"Command terminated by signal (\d+)", err)
    if signal:
        code = -int(signal.group(1))
    return {"limit_mb": limit_mb, "result": judge_run(code, out + err, expect), "exit": code,
            "peak_rss_mb": peak_rss_mb(err), "stderr_tail": err[-_TAIL:]}


def smallest_passing(runs: list[dict]) -> int | None:
    """The smallest limit at which this run and every larger limit passed."""
    best = None
    for item in sorted(runs, key=lambda r: r["limit_mb"], reverse=True):
        if item["result"] != "pass":
            break
        best = item["limit_mb"]
    return best


def measure(cmd: list[str], limits=DEFAULT_LIMITS_MB, expect: str | None = None, timeout: float = 900,
            sudo: bool = True, cgroup_root: Path | None = None) -> dict:
    if cgroup_root is not None:
        cgroup_setup(cgroup_root)
    runs = [run(cmd, limit, expect, timeout, sudo, cgroup_root) for limit in sorted(limits)]
    peaks = [r["peak_rss_mb"] for r in runs if r["result"] == "pass" and r["peak_rss_mb"] is not None]
    return {"command": cmd, "expect": expect, "runs": runs, "smallest_passing_mb": smallest_passing(runs),
            "peak_rss_mb": max(peaks) if peaks else None}
