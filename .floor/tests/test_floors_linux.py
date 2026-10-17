import json
import shutil
import subprocess
import sys

import pytest

from floor import memory, offline
from floor.cli import main

TIME_V = """\tCommand being timed: "whisper-cli"
\tMaximum resident set size (kbytes): 262144
\tExit status: 0
"""

TRACE = """1234  connect(3, {sa_family=AF_UNIX, sun_path="/var/run/nscd/socket"}, 110) = -1 ENOENT
1234  connect(4, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("140.82.112.3")}, 16) = -1 ENETUNREACH
1235  sendto(5, "x", 1, 0, {sa_family=AF_INET6, sin6_port=htons(53)}, 28) = -1 ENETUNREACH
1234  +++ exited with 0 +++
"""

linux_root_tools = pytest.mark.skipif(
    not sys.platform.startswith("linux") or not shutil.which("strace") or not shutil.which("unshare"),
    reason="needs Linux with strace and unshare")


def test_peak_rss_and_judge():
    assert memory.peak_rss_mb(TIME_V) == 256
    assert memory.peak_rss_mb("") is None
    assert memory.judge_run(0, "ask not what your country", "Ask not") == "pass"
    assert memory.judge_run(0, "nothing", "ask not") == "wrong-output"
    assert memory.judge_run(-9, "", None) == "oom"
    assert memory.judge_run(1, "", None) == "fail"


def test_smallest_passing():
    runs = [{"limit_mb": m, "result": r} for m, r in [(512, "oom"), (768, "pass"), (1024, "pass")]]
    assert memory.smallest_passing(runs) == 768
    runs.append({"limit_mb": 2048, "result": "fail"})
    assert memory.smallest_passing(runs) is None
    assert "MemoryMax=512M" in memory.wrapper(512)
    assert memory.wrapper(512, sudo=False)[0] == "systemd-run"


def test_cgroup_setup_moves_the_processes_first(tmp_path):
    (tmp_path / "cgroup.procs").write_text("1\n42\n", encoding="utf-8")
    (tmp_path / "cgroup.subtree_control").write_text("", encoding="utf-8")
    memory.cgroup_setup(tmp_path)
    assert (tmp_path / "floor-job" / "cgroup.procs").read_text(encoding="utf-8") == "42"  # one PID per write
    assert (tmp_path / "cgroup.subtree_control").read_text(encoding="utf-8") == "+memory"
    (tmp_path / "cgroup.subtree_control").write_text("memory pids", encoding="utf-8")
    (tmp_path / "cgroup.procs").write_text("7", encoding="utf-8")
    memory.cgroup_setup(tmp_path)  # already on: nothing moves
    assert (tmp_path / "floor-job" / "cgroup.procs").read_text(encoding="utf-8") == "42"


def test_cgroup_run_sets_the_limit_and_no_swap(tmp_path, monkeypatch):
    seen = {}

    def fake_run(argv, **kwargs):
        group = tmp_path / "floor-512"
        seen.update(argv=argv, max=(group / "memory.max").read_text(encoding="utf-8"),
                    swap=(group / "memory.swap.max").read_text(encoding="utf-8"))
        return subprocess.CompletedProcess(argv, 0, "And so, ask not what your country", TIME_V)

    monkeypatch.setattr(memory.subprocess, "run", fake_run)
    result = memory.run(["whisper-cli"], 512, expect="ask not", cgroup_root=tmp_path)
    assert result["result"] == "pass" and result["peak_rss_mb"] == 256
    assert seen["max"] == str(512 * 1024 * 1024) and seen["swap"] == "0"
    assert seen["argv"][:4] == memory.cgroup_wrapper(tmp_path / "floor-512")[:4]
    assert seen["argv"][-3:] == ["/usr/bin/time", "-v", "whisper-cli"]
    assert "sudo" not in seen["argv"]


@pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX shell")
def test_cgroup_wrapper_moves_the_command_itself(tmp_path):
    argv = memory.cgroup_wrapper(tmp_path)[:4] + ["sh", "-c", "echo $$"]
    pid = subprocess.run(argv, capture_output=True, text=True, check=True).stdout.strip()
    assert (tmp_path / "cgroup.procs").read_text(encoding="utf-8").strip() == pid


def test_network_attempts():
    attempts = offline.network_attempts(TRACE)
    assert len(attempts) == 2
    assert "AF_UNIX" not in "".join(attempts)


def test_download_mb(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"x" * 1_500_000)
    b.write_bytes(b"x" * 500_000)
    assert offline.download_mb([str(a), str(b)]) == 2.0
    (tmp_path / "lib").mkdir()
    c = tmp_path / "lib" / "a"
    c.write_bytes(b"x" * 10)
    assert offline.download_bytes([str(a), str(b), str(c)]) == {"a": 1_500_000, "b": 500_000, str(c): 10}


def test_judge_reads_memory_files(tmp_path, capsys):
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({"summary": {"floor": {"level": "x86-64-v1"}, "files": {"errors": []}}}), encoding="utf-8")
    tiny = tmp_path / "tiny.json"
    tiny.write_text(json.dumps({"model": "tiny", "runs": [], "smallest_passing_mb": 512, "peak_rss_mb": 177}),
                    encoding="utf-8")
    conn = tmp_path / "offline.json"
    conn.write_text(json.dumps({"offline": True, "network_attempts": 0, "download_mb": 81.9,
                                "download_bytes": {"ggml-tiny.en.bin": 77704715}}), encoding="utf-8")
    out = tmp_path / "judge.json"
    assert main(["judge", "--scan", str(scan), "--memory", str(tiny), "--connectivity", str(conn), "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["floors"]["memory"]["smallest_passing_mb"] == {"tiny": 512}
    assert doc["floors"]["memory"]["peak_rss_mb"] == {"tiny": 177}  # AC-F7
    assert doc["floors"]["connectivity"]["offline"] == "proven"
    assert doc["floors"]["connectivity"]["download_bytes"] == {"ggml-tiny.en.bin": 77704715}  # AC-F8
    assert doc["unmeasured"] == []


@linux_root_tools
def test_offline_catches_a_connect():
    script = "import socket; s = socket.socket(); s.settimeout(1)\ntry: s.connect(('1.1.1.1', 443))\nexcept OSError: pass\nprint('done')"
    result = offline.check([sys.executable, "-c", script], expect="done")
    assert result["traced"] and result["result"] == "pass"
    assert result["network_attempts"] >= 1 and not result["offline"]
    clean = offline.check([sys.executable, "-c", "print('done')"], expect="done")
    assert clean["offline"] and clean["network_attempts"] == 0
