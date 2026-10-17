import wave

from floor import energy
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
