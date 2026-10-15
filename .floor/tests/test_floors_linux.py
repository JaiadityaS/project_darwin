import json
import shutil
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


def test_network_attempts():
    attempts = offline.network_attempts(TRACE)
    assert len(attempts) == 2
    assert "AF_UNIX" not in "".join(attempts)


def test_download_mb(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_bytes(b"x" * 1_500_000)
    b.write_bytes(b"x" * 500_000)
    assert offline.download_mb([str(a), str(b)]) == 2.0


def test_judge_reads_memory_files(tmp_path, capsys):
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({"summary": {"floor": {"level": "x86-64-v1"}, "files": {"errors": []}}}), encoding="utf-8")
    tiny = tmp_path / "tiny.json"
    tiny.write_text(json.dumps({"model": "tiny", "runs": [], "smallest_passing_mb": 512}), encoding="utf-8")
    conn = tmp_path / "offline.json"
    conn.write_text(json.dumps({"offline": True, "network_attempts": 0}), encoding="utf-8")
    out = tmp_path / "judge.json"
    assert main(["judge", "--scan", str(scan), "--memory", str(tiny), "--connectivity", str(conn), "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["floors"]["memory"]["smallest_passing_mb"] == {"tiny": 512}
    assert doc["floors"]["connectivity"]["offline"] == "proven"
    assert doc["unmeasured"] == []


@linux_root_tools
def test_offline_catches_a_connect():
    script = "import socket; s = socket.socket(); s.settimeout(1)\ntry: s.connect(('1.1.1.1', 443))\nexcept OSError: pass\nprint('done')"
    result = offline.check([sys.executable, "-c", script], expect="done")
    assert result["traced"] and result["result"] == "pass"
    assert result["network_attempts"] >= 1 and not result["offline"]
    clean = offline.check([sys.executable, "-c", "print('done')"], expect="done")
    assert clean["offline"] and clean["network_attempts"] == 0
