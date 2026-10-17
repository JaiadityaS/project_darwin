from pathlib import Path

from floor import page
from floor.cli import main

ROOT = Path(__file__).resolve().parents[2]


def test_page_from_repo_evidence(tmp_path):
    target = page.build(ROOT / ".floor" / "evidence", tmp_path, ROOT / ".floor" / "notices", generated="2026-10-15")
    html = target.read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>")
    assert "<title>Rieux</title>" in html and "<h1>Rieux</h1>" in html  # the product name (D-013)
    assert "<script" not in html and "http://" not in html
    assert html.count("<circle") >= 100
    assert "H-1: the build machine sets the floor." in html
    assert "SIGILL" in html and "sandybridge" in html
    assert "**" not in html


def test_page_without_evidence(tmp_path):
    html = page.build(tmp_path / "none", tmp_path / "out", generated="x").read_text(encoding="utf-8")
    assert html.count("not measured yet") == 3
    assert "no release judged yet" in html


def test_timeline_svg_tooltip():
    rows = [{"ref": "main-abc", "created": "2026-01-01T00:00:00Z", "floor": "x86-64-v4", "extras": ["AVX512_VNNI"]},
            {"ref": "main-def", "created": "2026-02-01T00:00:00Z", "floor": "x86-64-v3", "extras": []}]
    svg = page.timeline_svg([("main", rows, "red")])
    assert svg.count("<circle") == 2 and "AVX512_VNNI" in svg


def test_cli(tmp_path):
    assert main(["page", "--evidence", str(tmp_path), "--out", str(tmp_path / "site")]) == 0
    assert (tmp_path / "site" / "index.html").exists()
