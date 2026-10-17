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
CPU_STAT = "usage_usec 2500000\nuser_usec 2000000\nsystem_usec 500000\nnr_periods 0\n"
MEMORY_STAT = "anon 104857600\nfile 314572800\nactive_file 104857600\ninactive_file 209715200\n"
JOB = {"measured_at": "2026-10-17T12:01:00+00:00", "wall_s": 100.0, "cpu_s": 150.0, "vcpus": 2, "vcpu_s": 200.0,
       "memory_gb_s": 50.0, "memory_peak_gb": 0.8, "cpu_model": "X", "scope": "cgroup", "evidence": "https://ci/jobs/1"}

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


def test_cgroup_readers():
    assert meter.cgroup_usage_us(CPU_STAT) == 2500000
    with pytest.raises(ValueError):
        meter.cgroup_usage_us("nr_periods 0\n")
    assert meter.cgroup_memory_gb(f"{3 * 2**30}\n", MEMORY_STAT) == 3 - 200 / 1024  # not the inactive file cache
    assert meter.cgroup_memory_gb("1024\n", MEMORY_STAT) == 0
    assert meter.cgroup_vcpus("max 100000\n", 4) == 4 and meter.cgroup_vcpus(None, 2) == 2
    assert meter.cgroup_vcpus("200000 100000\n", 4) == 2 and meter.cgroup_vcpus("150000 100000\n", 4) == 1.5
    assert meter.cgroup_vcpus("800000 100000\n", 4) == 4  # a quota above the CPUs that the group may use


def test_join_adds_the_jobs():
    probe = {**JOB, "measured_at": "2026-10-17T12:00:00+00:00", "wall_s": 50.0, "cpu_s": 20.0, "vcpu_s": 100.0,
             "memory_gb_s": 10.0, "memory_peak_gb": 1.2, "evidence": "https://ci/jobs/2"}
    doc = meter.join({"scan": JOB, "probe-qemu64": probe})
    assert (doc["wall_s"], doc["cpu_s"], doc["vcpu_s"], doc["memory_gb_s"]) == (150.0, 170.0, 300.0, 60.0)
    assert doc["vcpus"] == 2 and doc["memory_peak_gb"] == 1.2 and doc["cpu_model"] == "X" and doc["scope"] == "cgroup"
    assert doc["measured_at"] == "2026-10-17T12:00:00+00:00" and list(doc["jobs"]) == ["probe-qemu64", "scan"]
    assert doc["jobs"]["scan"]["evidence"] == "https://ci/jobs/1"
    inputs = footprint.release_inputs(doc)
    assert inputs["cpu/vcpus"] * inputs["duration"] == doc["vcpu_s"]  # the idle and embodied shares stay right
    mixed = meter.join({"scan": JOB, "probe": {**probe, "vcpus": 4, "vcpu_s": 200.0, "cpu_model": "Y"}})
    assert mixed["vcpus"] == round(400 / 150, 3) and mixed["cpu_model"] is None
    with pytest.raises(ValueError):
        meter.join({})


def test_cli_meter_join(tmp_path, capsys):
    for name in ("scan", "judge"):
        (tmp_path / f"{name}.json").write_text(json.dumps(JOB), encoding="utf-8")
    out, files = tmp_path / "meter.json", [str(tmp_path / "scan.json"), str(tmp_path / "judge.json")]
    assert main(["meter", "join", *files, "--evidence", "https://ci/pipelines/1", "--out", str(out)]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["wall_s"] == 200.0 and set(doc["jobs"]) == {"scan", "judge"} and doc["evidence"] == "https://ci/pipelines/1"
    assert "2 jobs: wall 200.0 s" in capsys.readouterr().out
    (tmp_path / "bad.json").write_text("{}", encoding="utf-8")
    assert main(["meter", "join"]) == 2 and main(["meter", "join", str(tmp_path / "bad.json")]) == 2
    assert main(["meter", "stop"]) == 2  # start, sample and stop need --state


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
    assert result["scope"] == "machine" and "samples" in capsys.readouterr().out
    assert not state.exists() and main(["meter", "stop", "--state", str(state)]) == 2  # a second stop: no meter


@linux
def test_meter_cgroup_scope(tmp_path, capsys):
    group, state = tmp_path / "group", tmp_path / "meter-state.json"
    group.mkdir()
    for name, text in {"cpu.stat": "usage_usec 1000000\n", "cpu.max": "150000 100000\n",
                       "memory.current": f"{2**30}\n", "memory.stat": "inactive_file 0\n"}.items():
        (group / name).write_text(text, encoding="utf-8")
    assert main(["meter", "start", "--cgroup", str(group), "--state", str(state), "--interval", "0.05"]) == 0
    assert f"cgroup {group.resolve()}" in capsys.readouterr().out
    (group / "cpu.stat").write_text("usage_usec 3500000\n", encoding="utf-8")  # the group used 2.5 s of CPU time
    deadline = time.monotonic() + 10
    while json.loads(meter.samples_path(state).read_text(encoding="utf-8"))["count"] < 3:
        assert time.monotonic() < deadline, "the sampler wrote no samples"
        time.sleep(0.05)
    result = meter.stop(state)
    assert result["cpu_s"] == 2.5 and result["scope"] == "cgroup" and result["memory_peak_gb"] == 1.0
    assert result["vcpus"] == min(1.5, len(os.sched_getaffinity(0)))
    assert not state.exists() and not meter.samples_path(state).exists()
    assert main(["meter", "start", "--cgroup", str(tmp_path), "--state", str(state)]) == 2  # no cpu.stat there


@linux
def test_stop_never_signals_another_process(tmp_path):
    state = tmp_path / "meter-state.json"
    meter._write_atomic(state, {"started_at": "2026-10-17T12:00:00+00:00", "t0": time.monotonic(), "busy_ticks": 0,
                                "clk_tck": 100, "vcpus": 1, "cpu_model": None, "interval_s": 5.0, "pid": os.getpid()})
    meter._write_atomic(meter.samples_path(state), {"t": time.monotonic(), "gb": 1.0, "gb_s": 0.0, "peak_gb": 1.0,
                                                    "count": 1})
    assert not meter._is_sampler(os.getpid(), state)
    assert meter.stop(state)["samples"] == 2  # this test process is still alive
