"""Tests for the registry client, without network access."""

from __future__ import annotations

import io
import json
import tarfile

import pytest
import requests
from elfbuild import build_elf

from floor.oci import Registry, app_layer, extract_elves, next_link


def _targz(entries) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            if data is None:
                info.type, info.linkname = tarfile.SYMTYPE, "whisper-cli"
                tar.addfile(info)
            else:
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def test_extract_elves_keeps_only_regular_elf_files_below_app(tmp_path):
    elf = build_elf(b"\xc3")
    blob = _targz([
        ("app/build/bin/whisper-cli", elf),
        ("./app/build/src/libwhisper.so", elf),
        ("app/models/ggml-base.en.bin", b"lmgg" + bytes(64)),
        ("app/build/bin/main", None),
        ("usr/lib/x86_64-linux-gnu/libc.so.6", elf),
        ("app/../evil.so", elf),
    ])
    written = extract_elves(io.BytesIO(blob), tmp_path)
    assert written == ["app/build/bin/whisper-cli", "app/build/src/libwhisper.so"]
    assert (tmp_path / "app" / "build" / "bin" / "whisper-cli").read_bytes() == elf
    assert not (tmp_path / "evil.so").exists()


def test_app_layer_matches_history_from_the_top():
    manifest = {"layers": [{"digest": "sha256:base"}, {"digest": "sha256:apt"}, {"digest": "sha256:app"}]}
    config = {"history": [
        {"created_by": "/bin/sh -c #(nop) ADD file:0a1b in / "},
        {"created_by": "/bin/sh -c #(nop)  CMD [\"/bin/bash\"]", "empty_layer": True},
        {"created_by": "RUN /bin/sh -c apt-get update # buildkit"},
        {"created_by": "WORKDIR /app", "empty_layer": True},
        {"created_by": "COPY /app /app # buildkit"},
        {"created_by": "ENTRYPOINT [\"bash\", \"-c\"]", "empty_layer": True},
    ]}
    layer, step = app_layer(manifest, config)
    assert layer["digest"] == "sha256:app"
    assert step.startswith("COPY /app /app")
    with pytest.raises(LookupError):
        app_layer(manifest, {"history": config["history"][:3]})


def test_next_link():
    header = '</v2/ggml-org/whisper.cpp/tags/list?last=main-abc&n=1000>; rel="next"'
    assert next_link(header) == "/v2/ggml-org/whisper.cpp/tags/list?last=main-abc&n=1000"
    assert next_link(None) is None


class _Response:
    def __init__(self, payload, headers=None, status=200):
        self.payload, self.headers, self.status_code = payload, headers or {}, status
        self.content = json.dumps(payload).encode()

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class _Session:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, params=None, headers=None, stream=False, timeout=None):
        self.calls.append(url)
        if url.endswith("/token"):
            return _Response({"token": "t"})
        return self.routes[url.split("/v2/ggml-org/whisper.cpp/", 1)[1]]


def test_platform_manifest_picks_linux_amd64_and_skips_attestations():
    index = {"manifests": [
        {"digest": "sha256:arm", "platform": {"os": "linux", "architecture": "arm64"}},
        {"digest": "sha256:att", "platform": {"os": "unknown", "architecture": "unknown"}},
        {"digest": "sha256:amd", "platform": {"os": "linux", "architecture": "amd64"}},
    ]}
    session = _Session({
        "manifests/main": _Response(index),
        "manifests/sha256:amd": _Response({"layers": []}, {"Docker-Content-Digest": "sha256:amd"}),
    })
    doc, digest = Registry(session=session).platform_manifest("main")
    assert (doc, digest) == ({"layers": []}, "sha256:amd")
    assert sum(url.endswith("/token") for url in session.calls) == 1


def test_tags_follow_link_pages():
    session = _Session({
        "tags/list?n=1000": _Response({"tags": ["main", "main-a1867e0"]},
                                      {"Link": '</v2/ggml-org/whisper.cpp/tags/list?last=main-a1867e0&n=1000>; rel="next"'}),
        "tags/list?last=main-a1867e0&n=1000": _Response({"tags": ["main-c62adfbd"]}),
    })
    assert Registry(session=session).tags() == ["main", "main-a1867e0", "main-c62adfbd"]
