import json
import wave
from pathlib import Path

import pytest

from floor import energy, footprint
from floor.cli import main


def _wav(path, frames: bytes, width: int = 2, rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(frames)


def test_repeat_wav(tmp_path):
    src, out = tmp_path / "a.wav", tmp_path / "b.wav"
    _wav(src, b"\x01\x02" * 1600)  # 0.1 s at 16 kHz, 16-bit
    assert energy.repeat_wav(src, out, copies=3, gap_s=0.05) == 0.4  # 3 x 0.1 s + 2 x 0.05 s
    with wave.open(str(out), "rb") as w:
        assert (w.getnframes(), w.getframerate(), w.getsampwidth(), w.getnchannels()) == (6400, 16000, 2, 1)
        data = w.readframes(6400)
    assert data[:3200] == data[4800:8000] == data[9600:] == b"\x01\x02" * 1600
    assert data[3200:4800] == data[8000:9600] == b"\x00" * 1600  # 800 frames of silence


def test_repeat_wav_8_bit_silence(tmp_path):
    src, out = tmp_path / "a.wav", tmp_path / "b.wav"
    _wav(src, b"\x10" * 800, width=1, rate=8000)
    energy.repeat_wav(src, out, copies=2, gap_s=0.1)
    with wave.open(str(out), "rb") as w:
        assert w.readframes(w.getnframes()) == b"\x10" * 800 + b"\x80" * 800 + b"\x10" * 800


def test_cli_audio(tmp_path, capsys):
    src = tmp_path / "a.wav"
    _wav(src, b"\x00\x00" * 16000)  # 1 s, like the 11 s of samples/jfk.wav in short
    assert main(["audio", str(src), str(tmp_path / "b.wav"), "--copies", "11", "--gap", "1"]) == 0
    assert "21.0 s (0.350 audio-minutes)" in capsys.readouterr().out
    assert main(["audio", str(src), str(tmp_path / "c.wav"), "--copies", "0"]) == 2
    (tmp_path / "bad.wav").write_bytes(b"not a wav file")
    assert main(["audio", str(tmp_path / "bad.wav"), str(tmp_path / "d.wav")]) == 2


def test_parse_time():
    assert energy.parse_time("4.52 7.80 0.41 152340\n") == {"wall_s": 4.52, "cpu_s": 8.21, "peak_rss_mb": 148.8}
    assert energy.parse_time("Command exited with non-zero status 1\n0.01 0.00 0.00 3200\n")["peak_rss_mb"] == 3.1
    assert energy.time_wrapper("t.txt")[-3:] == ["-f", energy.TIME_FORMAT, "--"]


def test_schedule_rotates_the_order():
    assert energy.schedule(["native", "folk", "all"], runs=3, warmup=1) == [
        (False, ["native", "folk", "all"]), (True, ["folk", "all", "native"]), (True, ["all", "native", "folk"]),
        (True, ["native", "folk", "all"])]


def test_cwd_backends(tmp_path):
    (tmp_path / "libggml-cpu-x64.so").write_bytes(b"")
    (tmp_path / "libggml-base.so").write_bytes(b"")
    assert energy.cwd_backends(tmp_path) == ["libggml-cpu-x64.so"]


def test_medians():
    runs = [{"wall_s": 3.0, "cpu_s": 5.0, "peak_rss_mb": 150.0}, {"wall_s": 1.0, "cpu_s": 2.0, "peak_rss_mb": 149.0},
            {"wall_s": 2.0, "cpu_s": 4.0, "peak_rss_mb": 151.0}]
    assert energy.medians(runs) == {"wall_s": 2.0, "cpu_s": 4.0, "peak_rss_mb": 150.0}


def test_measure_rounds_medians_and_failures(tmp_path):
    audio = tmp_path / "a.wav"
    _wav(audio, b"\x00\x00" * 48000)  # 3 s
    calls = []

    def fake_run(cmd, timeout):
        time_file, exe = cmd[2], cmd[6]
        assert cmd[7:9] == ["-m", "m.bin"] and cmd[-2:] == ["-f", str(audio)]
        calls.append(exe)
        n = calls.count(exe)
        Path(time_file).write_text(f"{n}.0 {2 * n}.0 0.5 {102400 * n}\n", encoding="utf-8")
        if exe == "/b/broken":
            return 1, "", "error"
        text = "other words" if exe == "/b/wrong" else " And so, my fellow Americans, ask not what your country can do"
        log = "load_backend: loaded CPU backend from /b/libggml-cpu-haswell.so" if exe == "/b/all" else ""
        return 0, text, log

    builds = {"native": "/b/native", "all": "/b/all", "broken": "/b/broken", "wrong": "/b/wrong"}
    doc = energy.measure(builds, ["-m", "m.bin"], str(audio), "ask not", runs=3, warmup=1, run=fake_run)
    assert calls[:4] == ["/b/native", "/b/all", "/b/broken", "/b/wrong"]
    assert calls[4:8] == ["/b/all", "/b/broken", "/b/wrong", "/b/native"]  # the order rotates
    native = doc["builds"]["native"]
    assert (native["wall_s"], native["cpu_s"], native["peak_rss_mb"]) == (3.0, 6.5, 300.0)  # not the warm-up run
    assert native["loaded_variant"] is None and len(native["transcript_sha256"]) == 1 and len(native["runs"]) == 3
    assert doc["builds"]["all"]["loaded_variant"] == "haswell"
    assert "wall_s" not in doc["builds"]["broken"] and "wall_s" not in doc["builds"]["wrong"]
    assert doc["audio_minutes"] == 0.05 and doc["runs_per_build"] == 3
    assert set(footprint.audio_inputs(doc)) == {"native", "all"}


def test_cli_energy_refuses_bad_input(tmp_path, monkeypatch, capsys):
    audio, exe = tmp_path / "a.wav", tmp_path / "cli"
    _wav(audio, b"\x00\x00" * 160)
    exe.write_bytes(b"")
    base = ["energy", "--audio", str(audio), "--runs", "1"]
    assert main([*base, "--build", "nameonly"]) == 2
    assert main([*base, "--build", f"a={tmp_path / 'missing'}"]) == 2
    assert main([*base, "--build", f"a={exe}", "--build", f"a={exe}"]) == 2  # one name twice
    assert main([*base, "--build", f"a={exe}", "--runs", "0"]) == 2
    monkeypatch.chdir(tmp_path)
    (tmp_path / "libggml-cpu-x64.so").write_bytes(b"")
    assert main([*base, "--build", f"a={exe}"]) == 2
    assert "libggml-cpu-x64.so" in capsys.readouterr().err


@pytest.mark.skipif(not Path("/usr/bin/time").is_file(), reason="needs GNU time (/usr/bin/time)")
def test_cli_energy_with_gnu_time(tmp_path, monkeypatch, capsys):
    audio, exe, out = tmp_path / "a.wav", tmp_path / "fake-cli", tmp_path / "energy.json"
    _wav(audio, b"\x00\x00" * 16000)
    exe.write_text("#!/bin/sh\necho ' ask not what your country can do for you'\n", encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.chdir(tmp_path)
    assert main(["energy", "--build", f"fake={exe}", "--audio", str(audio), "--expect", "ask not", "--runs", "2",
                 "--evidence", "https://ci/run/2", "--out", str(out), "--", "-m", "model.bin"]) == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    fake = doc["builds"]["fake"]
    assert fake["wall_s"] >= 0 and fake["peak_rss_mb"] > 0 and len(fake["runs"]) == 2 and fake["runs"][0]["exit"] == 0
    assert doc["evidence"] == "https://ci/run/2" and "pass" in capsys.readouterr().out
