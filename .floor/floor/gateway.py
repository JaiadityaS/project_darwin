"""Upload page and gateway of the Rieux demo service (F13.3, NFR-7, D-019).

whisper-server lets a client set its own parameters (for example `duration`) in the form, and it has
no rate limit. So whisper-server listens only on 127.0.0.1, and this gateway is the public port:
- GET /          the upload page (the browser makes 16 kHz mono WAV from a file or the microphone);
- POST /transcribe  a WAV body of at most 30 seconds; the gateway checks the length from the header and
                 the data size, then sends fixed parameters to whisper-server;
- GET /healthz   "ok" while whisper-server runs;
- GET /floor     the x86-64 level of the host CPU and the ggml CPU variant that whisper-server loaded,
                 from its log (F13.4).
Limits: a request rate per client and per instance, one transcription at a time per instance, and a
body size cap. Cloud Run caps the instances (infra/). Audio stays in memory: no file, no log
line, no copy after the answer. The log has the method, the path and the status only.

Standard library only, so the service image needs only python3 next to the held image:
    python3 gateway.py --serve      starts whisper-server, then the gateway on $PORT (default 8080)
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_SECONDS = 30
RATE = 16000
# 16-bit mono PCM at 16 kHz, plus room for the header and a few extra chunks.
MAX_BYTES = MAX_SECONDS * RATE * 2 + 4096
DRAIN_BYTES = 2 * 1024 * 1024  # a refused body up to this size is read and dropped (see do_POST)
PER_CLIENT = (6, 60.0)     # requests per seconds, for one client address
PER_INSTANCE = (30, 60.0)  # requests per seconds, for all clients of one instance
UPSTREAM = os.environ.get("WHISPER_URL", "http://127.0.0.1:8081/inference")
PAGE = Path(__file__).with_name("gateway.html")
# The /proc/cpuinfo flag names of the x86-64 psABI levels (pni is SSE3, abm is LZCNT), as in .gitlab/ci/facts.sh.
LEVEL_FLAGS = (
    ("x86-64-v2", {"cx16", "lahf_lm", "popcnt", "pni", "sse4_1", "sse4_2", "ssse3"}),
    ("x86-64-v3", {"avx", "avx2", "bmi1", "bmi2", "f16c", "fma", "abm", "movbe", "xsave"}),
    ("x86-64-v4", {"avx512f", "avx512bw", "avx512cd", "avx512dq", "avx512vl"}),
)
# The ggml backend loader names the file that it loaded: "load_backend: loaded CPU backend from .../libggml-cpu-haswell.so".
VARIANT_RE = re.compile(r"libggml-cpu-([A-Za-z0-9_]+)\.so")


class AudioError(ValueError):
    """The upload is not audio that the service accepts."""


def wav_seconds(data: bytes) -> float:
    """The length of a 16 kHz mono 16-bit PCM WAV file. Raises AudioError for every other input."""
    if len(data) > MAX_BYTES:
        raise AudioError(f"the file is larger than {MAX_BYTES} bytes")
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1, 2, RATE):
                raise AudioError("send 16 kHz mono 16-bit PCM WAV (the page makes it)")
            frames = w.getnframes()
            if len(w.readframes(frames)) != frames * 2:
                raise AudioError("the WAV data is shorter than its header says")
    except (wave.Error, EOFError) as exc:
        raise AudioError(f"not a WAV file: {exc}") from None
    seconds = frames / RATE
    if seconds > MAX_SECONDS:
        raise AudioError(f"the audio is {seconds:.1f} s; the limit is {MAX_SECONDS} s")
    if frames == 0:
        raise AudioError("the audio is empty")
    return seconds


class RateLimiter:
    """A sliding window: at most ``count`` requests in ``window`` seconds for each key. Memory stays small:
    keys with no request in the window are removed."""

    def __init__(self, count: int, window: float, clock=time.monotonic, max_keys: int = 10000):
        self.count, self.window, self.clock, self.max_keys = count, window, clock, max_keys
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self._lock:
            if len(self._hits) >= self.max_keys:
                self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > now - self.window}
                if len(self._hits) >= self.max_keys:
                    return False
            hits = [t for t in self._hits.get(key, []) if t > now - self.window]
            if len(hits) >= self.count:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


def client_key(forwarded_for: str | None, peer: str) -> str:
    """The client address. Cloud Run adds the address it sees as the last X-Forwarded-For entry; the
    entries before it come from the client, so they do not count."""
    if forwarded_for:
        last = forwarded_for.split(",")[-1].strip()
        if last:
            return last
    return peer


def inference_form(audio: bytes) -> tuple[bytes, str]:
    """The multipart form for whisper-server: the audio and fixed parameters only."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in (("response_format", "json"), ("temperature", "0.0")):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
                 "Content-Type: audio/wav\r\n\r\n".encode() + audio + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def transcribe(audio: bytes, url: str = UPSTREAM, timeout: float = 120.0) -> str:
    body, content_type = inference_form(audio)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": content_type}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        answer = json.loads(resp.read().decode("utf-8"))
    if "error" in answer:
        raise RuntimeError(str(answer["error"]))
    return str(answer.get("text", "")).strip()


def host_cpu(cpuinfo: str) -> dict:
    """The model and the x86-64 level of the first CPU in the text of /proc/cpuinfo. No flags: no level."""
    model, flags = None, None
    for line in cpuinfo.splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "model name" and model is None:
            model = value.strip()
        elif key.strip() == "flags" and flags is None:
            flags = set(value.split())
    level = None
    if flags is not None:
        level = "x86-64-v1"
        for name, needed in LEVEL_FLAGS:
            if not needed <= flags:
                break
            level = name
    return {"model": model, "level": level}


def loaded_variant(line: str) -> str | None:
    """The ggml CPU variant in a backend-loader line of the whisper-server log, else None."""
    if "load" in line.lower() and "cpu" in line.lower():
        match = VARIANT_RE.search(line)
        if match:
            return match.group(1)
    return None


def relay(stream, out, found: dict) -> None:
    """Copies the whisper-server log to `out` unchanged, and keeps the first ggml CPU variant that it names."""
    for raw in iter(stream.readline, b""):
        out.write(raw)
        out.flush()
        if found.get("variant") is None:
            found["variant"] = loaded_variant(raw.decode("utf-8", "replace"))


def floor_doc(host: dict, variant: str | None, ready: bool) -> dict:
    """The answer of GET /floor (F13.4). It reports only what the host and the log show."""
    doc = {"host_cpu": host.get("model"), "host_level": host.get("level"), "ggml_cpu_variant": variant,
           "source": "the flags of /proc/cpuinfo; the ggml backend-loader line of the whisper-server log"}
    if variant is None:
        doc["note"] = ("whisper-server is not ready yet" if not ready else
                       "the whisper-server log has no backend-loader line (a build without GGML_BACKEND_DL has none)")
    return doc


def read_cpuinfo(path: str = "/proc/cpuinfo") -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


class Gateway(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, upstream: str = UPSTREAM, per_client=PER_CLIENT, per_instance=PER_INSTANCE,
                 clock=time.monotonic, healthy=lambda: True, host: dict | None = None, found: dict | None = None):
        super().__init__(address, Handler)
        self.upstream, self.healthy = upstream, healthy
        self.host = host if host is not None else host_cpu(read_cpuinfo())
        self.found = found if found is not None else {}
        self.per_client = RateLimiter(*per_client, clock=clock)
        self.per_instance = RateLimiter(*per_instance, clock=clock)
        self.busy = threading.BoundedSemaphore(1)
        self.page = PAGE.read_bytes()


class Handler(BaseHTTPRequestHandler):
    server: Gateway
    server_version = "rieux-gateway"
    sys_version = ""

    def log_request(self, code="-", size="-"):
        # NFR-7: no client address, no headers, no audio. Method, path and status only.
        sys.stderr.write(f"{self.command} {self.path.split('?')[0]} {code}\n")

    def log_message(self, format, *args):  # noqa: A002 (the base class name)
        pass

    def _send(self, status: int, body: bytes, content_type: str, extra: dict[str, str] | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, doc: dict, extra: dict[str, str] | None = None):
        self._send(status, json.dumps(doc).encode("utf-8"), "application/json", extra)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self._send(200, self.server.page, "text/html; charset=utf-8",
                       {"Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; "
                        "style-src 'unsafe-inline'; font-src data:; media-src 'self' blob:; connect-src 'self'"})
        elif path == "/healthz":
            ok = self.server.healthy()
            self._send(200 if ok else 503, b"ok\n" if ok else b"starting\n", "text/plain")
        elif path == "/floor":
            self._json(200, floor_doc(self.server.host, self.server.found.get("variant"), self.server.healthy()))
        else:
            self._json(404, {"error": "not found"})

    do_HEAD = do_GET

    def do_POST(self):
        if self.path.split("?")[0] != "/transcribe":
            self._json(404, {"error": "not found"})
            return
        length = self.headers.get("Content-Length")
        if length is None or not length.isdigit():
            self._json(411, {"error": "send the WAV file with a Content-Length"})
            return
        if int(length) > MAX_BYTES:
            # Read and drop a body of moderate size, so the client gets the 413 and not a reset connection.
            # A larger body is not read: the connection closes.
            if int(length) <= DRAIN_BYTES:
                left = int(length)
                while left > 0:
                    chunk = self.rfile.read(min(left, 65536))
                    if not chunk:
                        break
                    left -= len(chunk)
            self.close_connection = True
            self._json(413, {"error": f"the limit is {MAX_SECONDS} s of 16 kHz mono WAV ({MAX_BYTES} bytes)"})
            return
        retry = {"Retry-After": "10"}
        if not self.server.per_client.allow(client_key(self.headers.get("X-Forwarded-For"), self.client_address[0])):
            self._json(429, {"error": f"at most {PER_CLIENT[0]} requests a minute"}, retry)
            return
        if not self.server.per_instance.allow("*"):
            self._json(429, {"error": "the service is busy; try again in a minute"}, retry)
            return
        audio = self.rfile.read(int(length))
        try:
            seconds = wav_seconds(audio)
        except AudioError as exc:
            self._json(400, {"error": str(exc)})
            return
        if not self.server.busy.acquire(timeout=20):
            self._json(503, {"error": "the service is busy; try again"}, retry)
            return
        try:
            started = time.monotonic()
            text = transcribe(audio, self.server.upstream)
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
            self._json(502, {"error": f"whisper-server: {type(exc).__name__}"})
            return
        finally:
            self.server.busy.release()
            del audio
        self._json(200, {"text": text, "audio_seconds": round(seconds, 2),
                         "processing_seconds": round(time.monotonic() - started, 2)})


def exit_text(code: int) -> str:
    """How whisper-server ended, for the log. SIGILL: this CPU has no instruction that the build used (H-1)."""
    if code >= 0:
        return f"whisper-server exited with code {code}"
    try:
        name = signal.Signals(-code).name
    except ValueError:
        name = f"signal {-code}"
    lacks = ": this CPU lacks an instruction that the build uses" if -code == signal.SIGILL else ""
    return f"whisper-server stopped by {name}{lacks}"


def serve(port: int, model: str, server_bin: str, threads: int) -> int:
    """Starts whisper-server on 127.0.0.1:8081 with a 30 s cap, then the gateway. Exits when whisper-server exits."""
    cmd = [server_bin, "-m", model, "--host", "127.0.0.1", "--port", "8081", "-t", str(threads),
           "-d", str(MAX_SECONDS * 1000), "--inference-path", "/inference"]
    child = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    found: dict = {}
    log = threading.Thread(target=relay, args=(child.stderr, sys.stderr.buffer, found), daemon=True)
    log.start()

    def healthy() -> bool:
        if child.poll() is not None:
            return False
        try:
            with urllib.request.urlopen("http://127.0.0.1:8081/", timeout=2):
                return True
        except (OSError, urllib.error.URLError):
            return False

    gateway = Gateway(("0.0.0.0", port), healthy=healthy, found=found)
    thread = threading.Thread(target=gateway.serve_forever, daemon=True)
    thread.start()
    print(f"rieux gateway on :{port}, whisper-server pid {child.pid}", file=sys.stderr, flush=True)
    code = child.wait()
    log.join(timeout=5)  # the last lines of the log come before the exit line
    print(exit_text(code), file=sys.stderr)
    gateway.shutdown()
    return code or 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--serve", action="store_true", help="start whisper-server and the gateway")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    ap.add_argument("--model", default=os.environ.get("WHISPER_MODEL", "/app/models/ggml-base.en.bin"))
    ap.add_argument("--server-bin", default=os.environ.get("WHISPER_SERVER", "whisper-server"))
    ap.add_argument("--threads", type=int, default=int(os.environ.get("WHISPER_THREADS", str(os.cpu_count() or 2))))
    args = ap.parse_args(argv)
    if not args.serve:
        ap.print_help()
        return 2
    return serve(args.port, args.model, args.server_bin, args.threads)


if __name__ == "__main__":
    sys.exit(main())
