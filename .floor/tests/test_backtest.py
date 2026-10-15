"""Tests for the backtest sampler and timeline, without network access."""

from __future__ import annotations

import json
from datetime import date

from floor.backtest import batches, choose, main_tags, parse_around, timeline
from floor.cli import main

SHA = "0123456789abcdef0123456789abcdef01234567"


def test_main_tags_keeps_only_cpu_main_builds():
    tags = ["main", f"main-{SHA}", f"main-cuda-{SHA}", f"main-intel-{SHA}", "main-a1867e0", "v1.8.2"]
    assert main_tags(tags) == [f"main-{SHA}"]


def test_parse_around():
    assert parse_around("2025-11-10:#3510") == (date(2025, 11, 10), "#3510")
    assert parse_around("2026-05-18") == (date(2026, 5, 18), "2026-05-18")


def _dated(n):
    return {f"main-{i:040x}": f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}T12:00:00Z" for i in range(n)}


def test_choose_spreads_evenly_and_keeps_both_ends():
    dated = _dated(100)
    chosen = choose(dated, count=10)
    assert len(chosen) == 10
    assert chosen[0]["created"] == "2025-01-01T12:00:00Z"
    assert chosen[-1]["ref"] == f"main-{99:040x}"
    assert [item["created"] for item in chosen] == sorted(item["created"] for item in chosen)


def test_choose_adds_every_image_near_a_report_and_skips_undated():
    dated = _dated(100)
    dated["main-undated"] = None
    chosen = choose(dated, count=2, around=[(date(2025, 2, 14), "#1")], window_days=3)
    near = [item for item in chosen if "near #1" in item["reasons"]]
    assert [item["created"][:10] for item in near] == [f"2025-02-{d}" for d in range(11, 18)]
    assert len(chosen) == 2 + 7
    assert all(item["ref"] != "main-undated" for item in chosen)


def test_batches():
    assert batches(list("abcde"), 2) == [["a", "b"], ["c", "d"], ["e"]]


def _report(path, ref, created, level):
    doc = {"image": {"ref": ref, "created": created, "manifest_digest": "sha256:x"},
           "summary": {"floor": {"level": level, "extras": [], "sources": []},
                       "baseline_variant": None, "highest_level_found": level}, "files": []}
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_timeline_orders_by_date_and_ignores_other_json(tmp_path, capsys):
    _report(tmp_path / "b.json", "main-b", "2025-11-09T21:41:00Z", "x86-64-v4")
    _report(tmp_path / "a.json", "main-a", "2025-10-28T20:48:00Z", "x86-64-v3")
    (tmp_path / "other.json").write_text("{\"images\": []}", encoding="utf-8")
    rows = timeline([str(tmp_path)])
    assert [(row["ref"], row["floor"]) for row in rows] == [("main-a", "x86-64-v3"), ("main-b", "x86-64-v4")]
    out = tmp_path / "out" / "timeline.json"
    assert main(["timeline", str(tmp_path), "--out", str(out)]) == 0
    assert len(json.loads(out.read_text(encoding="utf-8"))["images"]) == 3 - 1
    assert "main-b" in capsys.readouterr().out
