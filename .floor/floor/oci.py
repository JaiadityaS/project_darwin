"""Minimal client for public images on an OCI registry such as ghcr.io (PRD F10.1).

It fetches only what the backtest needs: tags, the linux/amd64 manifest, the image
config, and the one layer that holds /app. The layer is streamed. Only its ELF files
are written to disk, in a cache folder named after the layer digest.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath

import requests

REGISTRY = "https://ghcr.io"
DEFAULT_REPO = "ggml-org/whisper.cpp"
INDEX_TYPES = (
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
)
MANIFEST_TYPES = (
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
)
GZIP_LAYER_TYPES = (
    "application/vnd.oci.image.layer.v1.tar+gzip",
    "application/vnd.docker.image.rootfs.diff.tar.gzip",
)
# BuildKit writes `COPY --from=build /app /app` as "COPY /app /app # buildkit".
APP_STEP_RE = re.compile(r"\bCOPY (?:--\S+ )*/app /app\b")
ELF_MAGIC = b"\x7fELF"
_LINK_NEXT_RE = re.compile(r'<([^>]+)>\s*;\s*rel="next"')


def cache_root() -> Path:
    """FLOOR_CACHE if it is set, else ~/.cache/floor."""
    return Path(os.environ.get("FLOOR_CACHE") or Path.home() / ".cache" / "floor")


def next_link(header: str | None) -> str | None:
    """Returns the target of a rel="next" Link header, or None."""
    match = _LINK_NEXT_RE.search(header or "")
    return match.group(1) if match else None


class Registry:
    """Anonymous pull access to one repository."""

    def __init__(self, repo: str = DEFAULT_REPO, registry: str = REGISTRY, session: requests.Session | None = None):
        self.repo = repo
        self.registry = registry.rstrip("/")
        self.session = session or requests.Session()
        self._token: str | None = None

    def _auth(self) -> dict:
        if self._token is None:
            service = self.registry.split("://", 1)[-1]
            r = self.session.get(f"{self.registry}/token", timeout=30,
                                 params={"scope": f"repository:{self.repo}:pull", "service": service})
            r.raise_for_status()
            self._token = r.json()["token"]
        return {"Authorization": f"Bearer {self._token}"}

    def get(self, path: str, *, accept: str | None = None, stream: bool = False, timeout: float = 60) -> requests.Response:
        """GETs a path below /v2/<repo>/, or an absolute path such as a Link target.

        requests drops the Authorization header when a blob request redirects to another host.
        """
        url = f"{self.registry}{path}" if path.startswith("/") else f"{self.registry}/v2/{self.repo}/{path}"
        for attempt in range(2):
            headers = self._auth()
            if accept:
                headers["Accept"] = accept
            r = self.session.get(url, headers=headers, stream=stream, timeout=timeout)
            if r.status_code == 401 and attempt == 0:  # the token expired: get a new one once
                self._token = None
                continue
            r.raise_for_status()
            return r
        raise AssertionError("unreachable")

    def tags(self) -> list[str]:
        tags: list[str] = []
        path: str | None = "tags/list?n=1000"
        while path:
            r = self.get(path)
            tags.extend(r.json().get("tags") or [])
            path = next_link(r.headers.get("Link"))
        return tags

    def manifest(self, ref: str) -> tuple[dict, str]:
        """Returns (manifest or index, digest) for a tag or a digest."""
        r = self.get(f"manifests/{ref}", accept=", ".join(INDEX_TYPES + MANIFEST_TYPES))
        digest = r.headers.get("Docker-Content-Digest") or "sha256:" + hashlib.sha256(r.content).hexdigest()
        return r.json(), digest

    def platform_manifest(self, ref: str, os_name: str = "linux", arch: str = "amd64") -> tuple[dict, str]:
        """Resolves an index to the manifest of one platform. Attestation entries do not match."""
        doc, digest = self.manifest(ref)
        if "manifests" not in doc:
            return doc, digest
        for entry in doc["manifests"]:
            platform = entry.get("platform") or {}
            if platform.get("os") == os_name and platform.get("architecture") == arch:
                return self.manifest(entry["digest"])
        raise LookupError(f"{ref}: no {os_name}/{arch} manifest in the index")

    def blob(self, digest: str, *, stream: bool = False) -> requests.Response:
        return self.get(f"blobs/{digest}", stream=stream, timeout=300)


def app_layer(manifest: dict, config: dict) -> tuple[dict, str]:
    """Returns (layer descriptor, history step) of the runtime stage's `COPY /app /app` step.

    History entries with ``empty_layer`` make no layer. The two lists are matched from the
    top of the image down, because the top steps come from the project's Dockerfile.
    """
    steps = [h.get("created_by", "") for h in config.get("history", []) if not h.get("empty_layer")]
    for step, layer in zip(reversed(steps), reversed(manifest["layers"])):
        if APP_STEP_RE.search(step):
            return layer, step
    raise LookupError("no 'COPY /app /app' step in the image history")


def inspect_image(registry: Registry, ref: str) -> tuple[dict, dict]:
    """Returns (image facts, /app layer descriptor) for the linux/amd64 image of ``ref``."""
    manifest, digest = registry.platform_manifest(ref)
    config = registry.blob(manifest["config"]["digest"]).json()
    layer, step = app_layer(manifest, config)
    info = {
        "repo": registry.repo,
        "ref": ref,
        "manifest_digest": digest,
        "created": config.get("created"),
        "labels": (config.get("config") or {}).get("Labels") or {},
        "app_layer": {"digest": layer["digest"], "size": layer.get("size"),
                      "media_type": layer.get("mediaType"), "created_by": step},
    }
    return info, layer


class _HashingReader:
    """Passes reads through and hashes every byte, so that a layer is verified while it streams."""

    def __init__(self, raw):
        self.raw = raw
        self.sha256 = hashlib.sha256()

    def read(self, size: int = -1) -> bytes:
        data = self.raw.read(size)
        self.sha256.update(data)
        return data


def extract_elves(fileobj, dest: Path, prefix: str = "app/") -> list[str]:
    """Reads a gzip tar stream and writes its regular ELF files below ``prefix`` into ``dest``.

    The archive is untrusted: absolute names and names with '..' are skipped, and only
    regular files are written. Returns the written names, relative to ``dest``.
    """
    written = []
    with tarfile.open(fileobj=fileobj, mode="r|gz") as tar:
        for member in tar:
            name = member.name.removeprefix("./")
            parts = PurePosixPath(name).parts
            if not member.isreg() or not name.startswith(prefix) or ".." in parts:
                continue
            src = tar.extractfile(member)
            head = src.read(4) if src else b""
            if head != ELF_MAGIC:
                continue
            target = dest.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "wb") as out:
                out.write(head)
                shutil.copyfileobj(src, out, 1 << 20)
            written.append(name)
    return written


def pull_layer(registry: Registry, layer: dict, prefix: str = "app/") -> Path:
    """Downloads a layer once, verifies its digest, and keeps its ELF files in the cache."""
    media_type = layer.get("mediaType", "")
    if media_type not in GZIP_LAYER_TYPES:
        raise NotImplementedError(f"layer media type not supported: {media_type}")
    digest = layer["digest"]
    folder = cache_root() / "layers" / digest.replace(":", "-")
    if (folder / ".complete").exists():
        return folder
    part = folder.with_name(folder.name + ".part")
    shutil.rmtree(part, ignore_errors=True)
    part.mkdir(parents=True)
    with registry.blob(digest, stream=True) as response:
        response.raw.decode_content = False
        reader = _HashingReader(response.raw)
        files = extract_elves(reader, part, prefix)
        while reader.read(1 << 20):  # the rest of the stream (tar padding, gzip trailer)
            pass
    actual = "sha256:" + reader.sha256.hexdigest()
    if actual != digest:
        shutil.rmtree(part, ignore_errors=True)
        raise ValueError(f"layer digest mismatch: expected {digest}, got {actual}")
    (part / ".complete").write_text("\n".join(files) + "\n", encoding="utf-8")
    shutil.rmtree(folder, ignore_errors=True)
    part.rename(folder)
    return folder
