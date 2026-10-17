"""Energy per audio-minute (PRD F14.2, G7): native vs folk fix vs all-variants on the same hardware.

`floor audio` makes the test audio: the same speech file, repeated, with silence between the copies.
The helpers below are for `floor energy`: GNU time gives the wall time, the CPU time and the peak RSS
of each run, and the builds take turns in each round, in an order that rotates each round.
"""

from __future__ import annotations

import statistics
import wave
from pathlib import Path

TIME_FORMAT = "%e %U %S %M"  # GNU time: wall seconds, user seconds, system seconds, peak RSS in KB


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


def time_wrapper(out_file: str) -> list[str]:
    return ["/usr/bin/time", "-o", out_file, "-f", TIME_FORMAT, "--"]


def parse_time(text: str) -> dict:
    """The last line of a GNU time file. When the command fails, GNU time writes a line before it."""
    wall, user, system, rss_kb = text.strip().splitlines()[-1].split()
    return {"wall_s": float(wall), "cpu_s": round(float(user) + float(system), 3),
            "peak_rss_mb": round(int(rss_kb) / 1024, 1)}


def schedule(names: list[str], runs: int, warmup: int = 1) -> list[tuple[bool, list[str]]]:
    """The rounds as (counts, order). Each round runs every build once, and the order rotates by one
    each round, so no build always runs first. The first ``warmup`` rounds do not count."""
    return [(r >= warmup, names[r % len(names):] + names[:r % len(names)]) for r in range(warmup + runs)]


def cwd_backends(cwd: str | Path = ".") -> list[str]:
    """ggml also loads its CPU backends from the working directory, so these files change a run."""
    return sorted(path.name for path in Path(cwd).glob("libggml-cpu-*.so"))


def medians(runs: list[dict]) -> dict:
    return {key: round(statistics.median(run[key] for run in runs), 3) for key in ("wall_s", "cpu_s", "peak_rss_mb")}
