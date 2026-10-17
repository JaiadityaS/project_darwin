"""Energy per audio-minute (PRD F14.2, G7): native vs folk fix vs all-variants on the same hardware.

`floor audio` makes the test audio: the same speech file, repeated, with silence between the copies.
The helpers below are for `floor energy`: GNU time gives the wall time, the CPU time and the peak RSS
of each run, and the builds take turns in each round, in an order that rotates each round.
"""

from __future__ import annotations

import hashlib
import os
import signal
import statistics
import subprocess
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path

from . import meter, qemu

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


def audio_minutes(path: str | Path) -> float:
    with wave.open(str(path), "rb") as w:
        return round(w.getnframes() / w.getframerate() / 60, 4)


def _run(cmd: list[str], timeout: float) -> tuple[int | None, str, str]:
    """Run ``cmd`` in a new session. On a timeout, kill the whole group: GNU time and its child."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace",
                            start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, err = proc.communicate()
        return None, out, err
    return proc.returncode, out, err


def measure(builds: dict[str, str], args: list[str], audio: str, expect: str | None = None, runs: int = 5,
            warmup: int = 1, timeout: float = 900, run=_run) -> dict:
    """Run each build on ``audio`` (``EXE ARGS -f AUDIO``) under GNU time, and give the medians of the
    counted runs. A build with a failed run (an exit code, no expected text, a timeout) gets no medians,
    so `footprint.audio_inputs` leaves it out."""
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    found = {name: {"exe": exe, "runs": []} for name, exe in builds.items()}
    hashes: dict[str, set] = {name: set() for name in builds}
    with tempfile.TemporaryDirectory() as tmp:
        time_file = os.path.join(tmp, "time.txt")
        for counts, order in schedule(list(builds), runs, warmup):
            for name in order:
                if os.path.exists(time_file):
                    os.remove(time_file)
                code, out, err = run(time_wrapper(time_file) + [builds[name], *args, "-f", audio], timeout)
                if not counts:
                    continue
                try:
                    times = parse_time(Path(time_file).read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    times = {}
                ok = bool(times) and code == 0 and (not expect or expect.lower() in out.lower())
                found[name]["runs"].append({**times, "exit": code, "ok": ok})
                hashes[name].add(hashlib.sha256(out.encode("utf-8")).hexdigest())
                found[name].setdefault("loaded_variant", qemu.loaded_variant(err))
    for build in found.values():
        if all(run_["ok"] for run_ in build["runs"]):
            build.update(medians(build["runs"]))
    for name, build in found.items():
        build["transcript_sha256"] = sorted(hashes[name])
    cpuinfo = Path(meter.PROC_CPUINFO)
    return {"measured_at": started, "vcpus": os.cpu_count(),
            "cpu_model": meter.cpu_model(cpuinfo.read_text(encoding="utf-8")) if cpuinfo.exists() else None,
            "runs_per_build": runs, "warmup_rounds": warmup, "audio_minutes": audio_minutes(audio), "builds": found}
