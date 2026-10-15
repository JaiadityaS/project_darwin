"""Memory floor (PRD F7): the smallest cgroup memory limit at which a run still passes, and peak RSS.

Linux only. Each run goes into a transient systemd scope with MemoryMax and no swap, under
/usr/bin/time -v for the peak RSS. In CI the job runs as a user with sudo.
"""

from __future__ import annotations

import re
import subprocess

DEFAULT_LIMITS_MB = (512, 768, 1024, 1536, 2048, 3072, 4096)
_MAX_RSS = re.compile(r"Maximum resident set size \(kbytes\):\s*(\d+)")
_TAIL = 2000


def wrapper(limit_mb: int, sudo: bool = True) -> list[str]:
    cmd = ["systemd-run", "--scope", "--quiet", "--collect",
           "-p", f"MemoryMax={limit_mb}M", "-p", "MemorySwapMax=0"]
    return (["sudo", "--preserve-env"] if sudo else []) + cmd + ["--", "/usr/bin/time", "-v"]


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


def run(cmd: list[str], limit_mb: int, expect: str | None = None, timeout: float = 900, sudo: bool = True) -> dict:
    try:
        proc = subprocess.run(wrapper(limit_mb, sudo) + cmd, capture_output=True, text=True,
                              errors="replace", timeout=timeout)
        code, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        return {"limit_mb": limit_mb, "result": "timeout", "exit": None, "peak_rss_mb": None,
                "stderr_tail": (exc.stderr or b"")[-_TAIL:].decode("utf-8", "replace") if exc.stderr else ""}
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
            sudo: bool = True) -> dict:
    runs = [run(cmd, limit, expect, timeout, sudo) for limit in sorted(limits)]
    peaks = [r["peak_rss_mb"] for r in runs if r["result"] == "pass" and r["peak_rss_mb"] is not None]
    return {"command": cmd, "expect": expect, "runs": runs, "smallest_passing_mb": smallest_passing(runs),
            "peak_rss_mb": max(peaks) if peaks else None}
