import json
import os
import sys
import time

import pytest

from floor import footprint, meter
from floor.cli import main

STAT = "cpu  100 20 30 1000 50 5 7 3 0 0\ncpu0 50 10 15 500 25 2 3 1 0 0\n"
MEMINFO = "MemTotal:        8388608 kB\nMemFree:         1048576 kB\nMemAvailable:    6291456 kB\nHugePages_Total:       0\n"
CPUINFO = "processor\t: 0\nvendor_id\t: AuthenticAMD\nmodel name\t: AMD EPYC 7763 64-Core Processor\n"

linux = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="needs /proc (Linux)")


def test_proc_readers():
    assert meter.busy_ticks(STAT) == 100 + 20 + 30 + 5 + 7  # no idle, iowait or steal
    assert meter.memory_used_gb(MEMINFO) == 2.0
    assert meter.cpu_model(CPUINFO) == "AMD EPYC 7763 64-Core Processor"
    assert meter.cpu_model("processor\t: 0\n") is None
    with pytest.raises(ValueError):
        meter.busy_ticks("intr 1 2 3\n")


def test_trapezoid_and_totals():
    acc = {"t": 100.0, "gb": 1.0, "gb_s": 0.0, "peak_gb": 1.0, "count": 1}
    acc = meter.add(acc, 105.0, 3.0)
    assert acc["gb_s"] == 10.0 and acc["peak_gb"] == 3.0
    acc = meter.add(acc, 110.0, 1.0)
    assert acc["gb_s"] == 20.0 and acc["peak_gb"] == 3.0 and acc["count"] == 3
    state = {"started_at": "2026-10-17T12:00:00+00:00", "t0": 100.0, "busy_ticks": 1000, "clk_tck": 100, "vcpus": 2,
             "cpu_model": "AMD EPYC 7763 64-Core Processor", "interval_s": 5.0}
    result = meter.totals(state, acc, 110.0, 2500)
    assert result["wall_s"] == 10.0 and result["cpu_s"] == 15.0 and result["vcpu_s"] == 20.0
    assert result["memory_gb_s"] == 20.0 and result["memory_peak_gb"] == 3.0 and result["samples"] == 3
    assert footprint.release_inputs(result) == {
        "timestamp": "2026-10-17T12:00:00+00:00", "duration": 10.0, "cpu/vcpus": 2, "cpu/busy-seconds": 15.0,
        "memory/gb-seconds": 20.0, "release-checks": 1}


def test_meter_needs_a_state_file(tmp_path, capsys):
    if not os.path.exists(meter.PROC_STAT):
        assert main(["meter", "stop", "--state", str(tmp_path / "none.json")]) == 2
        assert "needs Linux" in capsys.readouterr().err
    else:
        assert main(["meter", "stop", "--state", str(tmp_path / "none.json")]) == 2
        assert "no meter state file" in capsys.readouterr().err


@linux
def test_meter_start_and_stop(tmp_path, capsys):
    state, out = tmp_path / "meter-state.json", tmp_path / "meter.json"
    assert main(["meter", "start", "--state", str(state), "--interval", "0.05"]) == 0
    pid = json.loads(state.read_text(encoding="utf-8"))["pid"]
    assert main(["meter", "start", "--state", str(state)]) == 2  # one sampler per state file
    deadline = time.monotonic() + 10
    while json.loads(meter.samples_path(state).read_text(encoding="utf-8"))["count"] < 3:
        assert time.monotonic() < deadline, "the sampler wrote no samples"
        time.sleep(0.05)
    assert main(["meter", "stop", "--state", str(state), "--evidence", "https://ci/run/1", "--out", str(out)]) == 0
    assert not meter._is_sampler(pid, state)
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["samples"] >= 4 and result["wall_s"] > 0 and result["memory_gb_s"] > 0
    assert result["vcpus"] == os.cpu_count() and result["cpu_s"] >= 0 and result["evidence"] == "https://ci/run/1"
    assert "samples" in capsys.readouterr().out


@linux
def test_stop_never_signals_another_process(tmp_path):
    state = tmp_path / "meter-state.json"
    meter._write_atomic(state, {"started_at": "2026-10-17T12:00:00+00:00", "t0": time.monotonic(), "busy_ticks": 0,
                                "clk_tck": 100, "vcpus": 1, "cpu_model": None, "interval_s": 5.0, "pid": os.getpid()})
    meter._write_atomic(meter.samples_path(state), {"t": time.monotonic(), "gb": 1.0, "gb_s": 0.0, "peak_gb": 1.0,
                                                    "count": 1})
    assert not meter._is_sampler(os.getpid(), state)
    assert meter.stop(state)["samples"] == 2  # this test process is still alive
