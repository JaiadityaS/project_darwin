"""Backtest sampling and timeline (PRD F10.1).

The sampler picks published `main-<sha>` images spread across time, plus every image
near the dates of known crash reports. The timeline joins the per-image JSON reports
of `floor image --out` into one list, ordered by build date.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import requests

from .oci import DEFAULT_REPO, Registry

MAIN_TAG_RE = re.compile(r"^main-[0-9a-f]{40}$")

# Crash reports that the backtest must cover (PRD §3.6): opening date and label.
DEFAULT_AROUND = (("2025-11-10", "#3510"), ("2026-05-18", "#3814"))


def main_tags(tags: list[str]) -> list[str]:
    """Returns the CPU image tags of `main` builds: `main-<40 hex>`."""
    return sorted(t for t in tags if MAIN_TAG_RE.match(t))


def _created(repo: str, ref: str) -> str | None:
    registry = Registry(repo)
    try:
        manifest, _ = registry.platform_manifest(ref)
        return registry.blob(manifest["config"]["digest"]).json().get("created")
    except (requests.RequestException, LookupError, ValueError, KeyError):
        return None


def image_dates(refs: list[str], repo: str = DEFAULT_REPO, workers: int = 8) -> dict[str, str | None]:
    """Reads the config `created` date of each image. The value is None if the read fails."""
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(zip(refs, pool.map(lambda ref: _created(repo, ref), refs)))


def _day(text: str) -> date:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).date()


def parse_around(text: str) -> tuple[date, str]:
    """Parses `YYYY-MM-DD` or `YYYY-MM-DD:label`."""
    day, _, label = text.partition(":")
    return date.fromisoformat(day), label or day


def choose(dated: dict[str, str | None], count: int = 30, around: list[tuple[date, str]] | None = None,
           window_days: int = 14) -> list[dict]:
    """Picks ``count`` images evenly spaced in time, plus every image within ``window_days``
    of a date in ``around``. Images without a date are skipped. Sorted by date."""
    items = sorted((created, ref) for ref, created in dated.items() if created)
    reasons: dict[str, list[str]] = {}
    for created, ref in items:
        for day, label in around or ():
            if abs((_day(created) - day).days) <= window_days:
                reasons.setdefault(ref, []).append(f"near {label}")
    n = len(items)
    if n and count > 0:
        picks = {round(i * (n - 1) / (count - 1)) for i in range(count)} if count > 1 else {n - 1}
        for index in sorted(picks):
            reasons.setdefault(items[index][1], []).append("spread")
    return [{"ref": ref, "created": created, "reasons": reasons[ref]} for created, ref in items if ref in reasons]


def batches(refs: list[str], size: int) -> list[list[str]]:
    return [refs[i:i + size] for i in range(0, len(refs), size)]


def _report_files(paths: list[str]) -> list[Path]:
    found = []
    for path in map(Path, paths):
        found.extend(sorted(path.rglob("*.json")) if path.is_dir() else [path])
    return found


def timeline(paths: list[str]) -> list[dict]:
    """Joins `floor image` reports into one row per image, ordered by build date."""
    rows = []
    for path in _report_files(paths):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or "image" not in doc or "summary" not in doc:
            continue
        image, summary = doc["image"], doc["summary"]
        rows.append({
            "ref": image["ref"],
            "created": image.get("created"),
            "manifest_digest": image.get("manifest_digest"),
            "floor": summary["floor"]["level"],
            "extras": summary["floor"]["extras"],
            "sources": summary["floor"]["sources"],
            "baseline_variant": summary.get("baseline_variant"),
            "highest_level_found": summary["highest_level_found"],
        })
    return sorted(rows, key=lambda row: (row["created"] or "", row["ref"]))
