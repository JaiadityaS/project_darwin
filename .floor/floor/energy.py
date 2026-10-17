"""Energy per audio-minute (PRD F14.2, G7): native vs folk fix vs all-variants on the same hardware.

`floor audio` makes the test audio: the same speech file, repeated, with silence between the copies.
"""

from __future__ import annotations

import wave
from pathlib import Path


def repeat_wav(src: str | Path, out: str | Path, copies: int = 11, gap_s: float = 1.0) -> float:
    """Write ``copies`` copies of ``src`` with ``gap_s`` seconds of silence between them.

    Returns the length of ``out`` in seconds. 8-bit PCM is unsigned, so its silence is 0x80, not 0x00.
    """
    if copies < 1 or gap_s < 0:
        raise ValueError(f"copies must be 1 or more and the gap 0 s or more, not {copies} and {gap_s}")
    with wave.open(str(src), "rb") as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
    if params.comptype != "NONE":
        raise ValueError(f"{src}: compressed WAV ({params.comptype}) is not supported")
    frame_bytes = params.nchannels * params.sampwidth
    silence = (b"\x80" if params.sampwidth == 1 else b"\x00") * (round(gap_s * params.framerate) * frame_bytes)
    body = silence.join([frames] * copies)
    with wave.open(str(out), "wb") as w:
        w.setparams(params)
        w.writeframes(body)
    return len(body) // frame_bytes / params.framerate
