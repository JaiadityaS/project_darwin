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
