"""Connectivity tripwire (PRD F8): the run must pass with no network, and it must not try to connect.

Linux only. The command runs in a new network namespace (only a down loopback) under strace.
Every connect/sendto/sendmsg to an AF_INET or AF_INET6 address counts as a network attempt.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path

from .memory import judge_run

_TRACE = "trace=connect,sendto,sendmsg"
_INET_CALL = re.compile(r"\b(connect|sendto|sendmsg)\(\d+,.*?sa_family=AF_INET6?\b")
_TAIL = 2000


def wrapper(trace_file: str, sudo: bool = True) -> list[str]:
    cmd = ["unshare", "--net", "--", "strace", "-f", "-q", "-e", _TRACE, "-o", trace_file]
    return (["sudo", "--preserve-env"] if sudo else []) + cmd


def network_attempts(trace: str) -> list[str]:
    return [line.strip() for line in trace.splitlines() if _INET_CALL.search(line)]


def download_mb(paths: list[str]) -> float:
    """What a user must download before the first offline run (binary, libraries, model)."""
    total = sum(os.path.getsize(p) for p in paths)
    return round(total / 1_000_000, 1)


def check(cmd: list[str], expect: str | None = None, artifacts: list[str] | None = None, timeout: float = 900,
          sudo: bool = True) -> dict:
    with tempfile.TemporaryDirectory() as folder:
        trace_file = str(Path(folder) / "trace.txt")
        try:
            proc = subprocess.run(wrapper(trace_file, sudo) + cmd, capture_output=True, text=True,
                                  errors="replace", timeout=timeout)
            code, output, err = proc.returncode, proc.stdout + proc.stderr, proc.stderr
        except subprocess.TimeoutExpired:
            code, output, err = None, "", "timeout"
        trace = Path(trace_file).read_text(encoding="utf-8", errors="replace") if Path(trace_file).exists() else ""
    attempts = network_attempts(trace)
    traced = "+++ exited with" in trace
    result = "timeout" if code is None else judge_run(code, output, expect)
    return {
        "command": cmd,
        "result": result,
        "exit": code,
        "offline": result == "pass" and traced and not attempts,  # no trace = not proven
        "network_attempts": len(attempts),
        "attempts": attempts[:20],
        "traced": traced,
        "download_mb": download_mb(artifacts) if artifacts else None,
        "stderr_tail": err[-_TAIL:],
    }
