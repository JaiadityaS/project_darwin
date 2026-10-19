import io
import json
import threading
import urllib.error
import urllib.request
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from floor import gateway


def make_wav(seconds: float, rate: int = 16000, channels: int = 1, width: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(b"\x00\x01" * int(seconds * rate) * channels * (width // 2 or 1))
    return buf.getvalue()


def test_wav_seconds():
    assert gateway.wav_seconds(make_wav(2.5)) == 2.5
    assert gateway.wav_seconds(make_wav(30)) == 30
    for data, message in ((make_wav(30.1), "the limit is 30 s"), (make_wav(1, rate=44100), "16 kHz mono"),
                          (make_wav(1, channels=2), "16 kHz mono"), (b"RIFF....WAVE", "not a WAV file"),
                          (make_wav(0), "empty"), (make_wav(2)[:-100], "shorter than its header"),
                          (b"\x00" * (gateway.MAX_BYTES + 1), "larger than")):
        with pytest.raises(gateway.AudioError, match=message):
            gateway.wav_seconds(data)


def test_rate_limiter_window_and_memory():
    now = [0.0]
    limiter = gateway.RateLimiter(2, 60.0, clock=lambda: now[0], max_keys=3)
    assert limiter.allow("a") and limiter.allow("a") and not limiter.allow("a")
    assert limiter.allow("b")
    now[0] = 61.0
    assert limiter.allow("a")
    assert limiter.allow("c") and limiter.allow("d")
    assert len(limiter._hits) <= 3  # old keys are removed


def test_client_key_uses_the_address_that_cloud_run_adds():
    assert gateway.client_key("6.6.6.6, 203.0.113.9", "10.0.0.1") == "203.0.113.9"
    assert gateway.client_key(None, "10.0.0.1") == "10.0.0.1"
    assert gateway.client_key(" ", "10.0.0.1") == "10.0.0.1"


class FakeWhisper(BaseHTTPRequestHandler):
    """whisper-server's /inference: records the form it gets."""
    forms: list = []
    answer = {"text": " ask not what your country can do for you\n"}

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        FakeWhisper.forms.append((self.headers["Content-Type"], body))
        data = json.dumps(FakeWhisper.answer).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def service():
    fake = ThreadingHTTPServer(("127.0.0.1", 0), FakeWhisper)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    gw = gateway.Gateway(("127.0.0.1", 0), upstream=f"http://127.0.0.1:{fake.server_port}/inference",
                         per_client=(3, 60.0), per_instance=(5, 60.0))
    threading.Thread(target=gw.serve_forever, daemon=True).start()
    FakeWhisper.forms = []
    yield f"http://127.0.0.1:{gw.server_port}"
    gw.shutdown()
    fake.shutdown()


def call(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read()


def test_page_and_health(service):
    status, headers, body = call(service + "/")
    assert status == 200 and b"At most 30 seconds" in body and headers["Cache-Control"] == "no-store"
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert call(service + "/healthz")[0] == 200
    assert call(service + "/nothing")[0] == 404


def test_transcribe_sends_fixed_parameters_only(service):
    status, _, body = call(service + "/transcribe?duration=999999", make_wav(1.5), {"Content-Type": "audio/wav"})
    assert status == 200
    doc = json.loads(body)
    assert doc["text"] == "ask not what your country can do for you" and doc["audio_seconds"] == 1.5
    content_type, form = FakeWhisper.forms[0]
    assert content_type.startswith("multipart/form-data; boundary=")
    names = [part.split(b'"')[1] for part in form.split(b"Content-Disposition: form-data; name=")[1:]]
    assert names == [b"response_format", b"temperature", b"file"]
    assert b"duration" not in form.replace(make_wav(1.5), b"")


def test_limits(service):
    wav = make_wav(1)
    # The size cap comes first, before the body is read, and it does not count as a request.
    assert call(service + "/transcribe", make_wav(31))[0] == 413
    req = urllib.request.Request(service + "/transcribe", data=b"x", method="POST",
                                 headers={"Content-Length": str(gateway.DRAIN_BYTES + 1)})  # not read
    with pytest.raises(urllib.error.HTTPError) as too_big:
        urllib.request.urlopen(req, timeout=10)
    assert too_big.value.code == 413
    # Inside the size cap, the length check reads the WAV header.
    assert json.loads(call(service + "/transcribe", make_wav(30.05))[2])["error"].endswith("the limit is 30 s")
    assert json.loads(call(service + "/transcribe", b"x" * 10)[2])["error"].startswith("not a WAV file")
    # Per client: 3 a minute (the two 400s count). Another client address still gets through.
    assert call(service + "/transcribe", wav)[0] == 200
    status, headers, _ = call(service + "/transcribe", wav)
    assert status == 429 and headers["Retry-After"] == "10"
    assert call(service + "/transcribe", wav, {"X-Forwarded-For": "6.6.6.6, 198.51.100.7"})[0] == 200
    assert call(service + "/transcribe", wav, {"X-Forwarded-For": "198.51.100.8"})[0] == 200
    # Per instance: 5 a minute for all clients.
    status, _, body = call(service + "/transcribe", wav, {"X-Forwarded-For": "198.51.100.9"})
    assert status == 429 and b"busy" in body
    assert len(FakeWhisper.forms) == 3  # only the valid requests reached whisper-server


def test_upstream_error_is_502(service):
    FakeWhisper.answer = {"error": "failed to read audio data"}
    try:
        status, _, body = call(service + "/transcribe", make_wav(1))
    finally:
        FakeWhisper.answer = {"text": " ask not what your country can do for you\n"}
    assert status == 502 and json.loads(body)["error"] == "whisper-server: RuntimeError"


def test_main_needs_serve(capsys):
    assert gateway.main([]) == 2
    assert "--serve" in capsys.readouterr().out


def test_service_image_recipe():
    """The service image has only python3 next to the held image, so the gateway uses the standard library only."""
    import ast
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse(Path(gateway.__file__).read_text(encoding="utf-8"))
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert names - {"__future__"} <= set(sys.stdlib_module_names)
    recipe = (root / "deploy/service.Dockerfile").read_text(encoding="utf-8")
    assert "COPY .floor/floor/gateway.py .floor/floor/gateway.html /srv/rieux/" in recipe
    assert 'ENTRYPOINT ["python3", "/srv/rieux/gateway.py", "--serve"]' in recipe
    assert "FROM ${IMAGE}" in recipe and (root / ".floor/floor/gateway.html").exists()


def test_service_ci_job():
    """T-52: GitLab CI runs the service image with the real whisper-server (a smoke test)."""
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parents[2]
    ci = yaml.safe_load((root / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    job = ci["service"]
    assert job["needs"] == ["build"] and job["artifacts"]["paths"] == ["out/service/"]
    script = job["script"][0]
    assert '-f deploy/service.Dockerfile --build-arg IMAGE="$IMAGE_REF"' in script
    assert "--data-binary @samples/jfk.wav http://docker:8080/transcribe" in script and 'grep -qi "$EXPECT"' in script
    assert "--post-file" not in script  # BusyBox wget cuts binary bodies at the first zero byte
    assert "docker push" not in script
    # Pipeline 2961114166: the container stopped while it loaded the model. The job now records its
    # CPU and the exit state, so the cause is evidence and not a guess.
    assert "sh .gitlab/ci/facts.sh --cpu | tee out/service/cpu.txt" in script
    assert "{{.State.ExitCode}}" in script and "> out/service/service.log" in script
    # F13.4 (D-028): the job keeps what GET /floor reports, after the backend has loaded.
    assert script.index("curl -sS -o out/service/floor.json http://docker:8080/floor") > script.index("/transcribe)")
    assert '"host_level": "x86-64-v' in script


def test_exit_text():
    assert gateway.exit_text(0) == "whisper-server exited with code 0"
    assert gateway.exit_text(-4) == "whisper-server stopped by SIGILL: this CPU lacks an instruction that the build uses"
    assert gateway.exit_text(-200) == "whisper-server stopped by signal 200"


V1 = "fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse sse2 syscall nx lm"
V2 = V1 + " pni ssse3 cx16 sse4_1 sse4_2 popcnt lahf_lm"
V3 = V2 + " avx avx2 bmi1 bmi2 f16c fma abm movbe xsave"
V4 = V3 + " avx512f avx512bw avx512cd avx512dq avx512vl avx512_fp16"


def test_host_cpu():
    """F13.4: the same flag rule as .gitlab/ci/facts.sh; the first CPU counts."""
    def info(flags, model="Intel(R) Xeon(R) Platinum 8581C CPU @ 2.10GHz"):
        cpu = f"processor\t: 0\nmodel name\t: {model}\nflags\t\t: {flags}\n\n"
        return cpu + cpu.replace("processor\t: 0", "processor\t: 1")
    assert gateway.host_cpu(info(V4)) == {"model": "Intel(R) Xeon(R) Platinum 8581C CPU @ 2.10GHz", "level": "x86-64-v4"}
    assert gateway.host_cpu(info(V3))["level"] == "x86-64-v3"
    assert gateway.host_cpu(info(V2))["level"] == "x86-64-v2"
    assert gateway.host_cpu(info(V1))["level"] == "x86-64-v1"
    assert gateway.host_cpu(info(V3.replace(" abm", "")))["level"] == "x86-64-v2"  # no LZCNT: not v3
    assert gateway.host_cpu(info(V4.replace(" avx512vl", "")))["level"] == "x86-64-v3"
    assert gateway.host_cpu("") == {"model": None, "level": None}


def test_relay_keeps_the_log_and_the_variant():
    log = (b"whisper_init_from_file_with_params_no_state: loading model\n"
           b"load_backend: loaded CPU backend from /app/build/bin/libggml-cpu-haswell.so\n"
           b"load_backend: loaded CPU backend from /app/build/bin/libggml-cpu-x64.so\n"
           b"\xff not UTF-8\n")
    out, found = io.BytesIO(), {}
    gateway.relay(io.BytesIO(log), out, found)
    assert out.getvalue() == log and found == {"variant": "haswell"}
    assert gateway.loaded_variant("whisper_model_load: n_mels = 80") is None


def test_floor_endpoint():
    host = {"model": "Intel(R) Xeon(R) Platinum 8581C CPU @ 2.10GHz", "level": "x86-64-v4"}
    found, ready = {}, [False]
    gw = gateway.Gateway(("127.0.0.1", 0), healthy=lambda: ready[0], host=host, found=found)
    threading.Thread(target=gw.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{gw.server_port}/floor"
    try:
        doc = json.loads(call(url)[2])
        assert doc["host_level"] == "x86-64-v4" and doc["ggml_cpu_variant"] is None
        assert doc["note"] == "whisper-server is not ready yet"
        ready[0] = True
        assert "no backend-loader line" in json.loads(call(url)[2])["note"]
        found["variant"] = "haswell"
        status, headers, body = call(url)
        doc = json.loads(body)
        assert status == 200 and headers["Cache-Control"] == "no-store"
        assert doc["ggml_cpu_variant"] == "haswell" and "note" not in doc and doc["host_cpu"] == host["model"]
    finally:
        gw.shutdown()


def test_page_shows_the_server_cpu():
    page = gateway.PAGE.read_text(encoding="utf-8")
    assert 'fetch("/floor")' in page and 'id="host"' in page
