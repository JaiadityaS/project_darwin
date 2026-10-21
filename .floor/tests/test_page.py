import json
from pathlib import Path

from floor import page
from floor.cli import main

ROOT = Path(__file__).resolve().parents[2]


def _run(wall, cpu, rss=500.0, ok=True):
    return {"wall_s": wall, "cpu_s": cpu, "peak_rss_mb": rss, "exit": 0 if ok else 1, "ok": ok}


ENERGY = {"measured_at": "2026-10-17T12:00:00+00:00", "vcpus": 4, "cpu_model": "AMD EPYC 7763 64-Core Processor",
          "runs_per_build": 2, "warmup_rounds": 1, "audio_minutes": 2.0,
          "builds": {
              "x64-only": {"exe": "x", "runs": [_run(90, 300)] * 2, "loaded_variant": "x64",
                           "wall_s": 90.0, "cpu_s": 300.0, "peak_rss_mb": 500.0},
              "all-variants": {"exe": "a", "runs": [_run(40, 148), _run(40, 152)], "loaded_variant": "haswell",
                               "wall_s": 40.0, "cpu_s": 150.0, "peak_rss_mb": 510.0},
              "folk-fix": {"exe": "f", "runs": [_run(40, 118), _run(40, 122)], "loaded_variant": None,
                           "wall_s": 40.0, "cpu_s": 120.0, "peak_rss_mb": 505.0},
              "native": {"exe": "n", "runs": [_run(40, 118), _run(1, 1, ok=False)], "loaded_variant": None}}}


def _row(unit, child, headline, energy_kwh, units, sci_g):
    return {"manifest": f"floor-sci-{unit[:-1]}", "child": child, "unit": unit, "headline": headline,
            "region": "us-central1", "grid_gco2e_per_kwh": 413.0, "energy_kwh": energy_kwh,
            "operational_gco2e": 0.1, "embodied_gco2e": 0.01, "carbon_gco2e": sci_g * units,
            "functional_units": units, "sci_gco2e": sci_g}


SCI = {"method": "GSF Impact Framework (test)", "sci_gco2e_per_audio_minute": 0.0512,
       "sci_gco2e_per_release_check": 3.25, "regions": {"audio-minutes": "us-central1", "release-checks": "us-central1"},
       "rows": [_row("audio-minutes", "all-variants", True, 0.00025, 2.0, 0.0512),
                _row("audio-minutes", "folk-fix", False, 0.0002, 2.0, 0.041),
                _row("release-checks", "release-check", True, 0.0078, 1.0, 3.25)]}


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
    # F14.4: the one-off footprint of the backtest (floor backtest-footprint).
    assert "the scans downloaded 27.5 GB (one config and one /app layer per image) in 18 runner-minutes" in html


def test_page_without_evidence(tmp_path):
    html = page.build(tmp_path / "none", tmp_path / "out", generated="x").read_text(encoding="utf-8")
    assert html.count("not measured yet") == 6
    assert "no release judged yet" in html


def test_page_energy_and_sci(tmp_path):
    for path, doc in (("energy/energy.json", ENERGY), ("footprint/sci.json", SCI)):
        (tmp_path / path).parent.mkdir()
        (tmp_path / path).write_text(json.dumps(doc))
    html = page.build(tmp_path, tmp_path / "out", generated="x").read_text(encoding="utf-8")
    assert "<script" not in html and html.count("not measured yet") == 4  # H-1, backtest, CPU proof, languages
    energy = html.split("the cost of inclusion</h2>")[1].split("<h2>")[0]
    # The builds in the order of F14.2. native has a failed run, so it has no medians and no ratio.
    assert [energy.index(f"<b>{n}</b>") for n in page.BUILDS] == sorted(energy.index(f"<b>{n}</b>") for n in page.BUILDS)
    assert "no result" in energy and "1 of 2 runs failed" in energy
    # all-variants against folk-fix: CPU time 150 / 120, energy (0.25 / 2) / (0.2 / 2) Wh per audio-minute.
    # The noise: folk-fix runs 118 and 122 s, (122 - 118) / 120 = 3.3%. 25% is more than that.
    assert "The cost of inclusion: +25.0% CPU time, +25.0% energy per audio-minute</b>" in energy
    assert "differ by up to 3.3%, so this difference is outside the noise" in energy
    assert "<td>75.0</td><td>20.0</td><td>0.125</td><td>510</td><td>haswell</td><td>2.7%</td><td>+25.0%</td>" in energy
    assert "<td>60.0</td><td>20.0</td><td>0.1</td><td>505</td><td>built in</td><td>3.3%</td><td>-</td>" in energy
    assert "<td>0.0%</td><td>2.5×</td>" in energy  # x64-only: the same two runs, 300 / 120
    assert "needs 2.0× the CPU time of all-variants" in energy  # 300 / 150
    assert "AMD EPYC 7763" in energy and "Median of 2 runs" in energy
    sci = html.split("Footprint (SCI)</h2>")[1].split("<h2>")[0]
    assert "<b>0.0512</b>g CO2e per audio-minute (us-central1)" in sci
    assert "<b>3.25</b>g CO2e per release check" in sci
    assert "all-variants (headline)" in sci and "folk-fix (headline)" not in sci
    assert "<td>7.8</td>" in sci  # 0.0078 kWh as Wh
    assert "GSF Impact Framework (test)" in sci


def test_page_energy_without_sci(tmp_path):
    doc = json.loads(json.dumps(ENERGY))
    doc["builds"]["all-variants"]["cpu_s"] = 121.0
    (tmp_path / "energy").mkdir()
    (tmp_path / "energy" / "energy.json").write_text(json.dumps(doc))
    html = page.build(tmp_path, tmp_path / "out", generated="x").read_text(encoding="utf-8")
    assert "The cost of inclusion: +0.8% CPU time per audio-minute</b>" in html  # no if-run results: no energy ratio
    assert "so this difference is inside the noise" in html  # 0.8% is less than 3.3%
    assert "SCI: not measured yet." in html


def test_page_energy_from_repo_evidence(tmp_path):
    html = page.build(ROOT / ".floor" / "evidence", tmp_path, generated="x").read_text(encoding="utf-8")
    energy = html.split("the cost of inclusion</h2>")[1].split("<h2>")[0]
    assert "not measured yet" not in energy and "no result" not in energy
    assert all(f"<b>{name}</b>" in energy for name in page.BUILDS)


def test_page_language_table(tmp_path):
    row = {"language": "sw", "name": "swahili", "fleurs": "sw_ke", "size": "small", "clips": 50, "words": 1000,
           "wer_f16": 0.28, "cer_f16": 0.09, "wer_quant": 0.312, "drift": 0.032, "drift_ci": [0.011, 0.054],
           "served_f16": True, "served_quant": False, "missing": 1, "bad_utf8": 2}
    doc = {"usable_wer": 0.3, "quant": "q5_1", "decoding": "-l <lang> -nf -bs 5 -bo 5 -t 2", "commit": "0c7be696abc",
           "rows": [row, {**row, "size": "tiny", "wer_f16": 0.61, "wer_quant": 0.65, "served_f16": False,
                          "missing": 0, "bad_utf8": 0}],
           "served": ["swahili"], "not_served": [], "not_measured": ["english", "yoruba"]}
    (tmp_path / "language").mkdir()
    (tmp_path / "language" / "language.json").write_text(json.dumps(doc))
    html = page.build(tmp_path, tmp_path / "out", generated="x").read_text(encoding="utf-8")
    lang = html.split("<h2>Languages</h2>")[1].split("<h2>")[0]
    assert "not measured yet" not in lang
    assert "<b>Served</b> (f16 WER at most 30%): swahili." in lang
    assert ('<td>28.0%</td><td>9.0%</td><td>31.2%</td><td>+3.2 <span class="mute">[+1.1, +5.4]</span></td>'
            '<td><span class="pass">yes</span> <span class="inc">(no at q5_1)</span></td>') in lang
    assert "50 sentences per language" in lang and "<code>0c7be696</code>" in lang
    assert "2 transcript(s) had bytes that are not UTF-8" in lang
    assert "1 clip(s) gave no transcript" in lang and "Not measured: 2 other whisper languages" in lang


def test_timeline_svg_tooltip():
    rows = [{"ref": "main-abc", "created": "2026-01-01T00:00:00Z", "floor": "x86-64-v4", "extras": ["AVX512_VNNI"]},
            {"ref": "main-def", "created": "2026-02-01T00:00:00Z", "floor": "x86-64-v3", "extras": []}]
    svg = page.timeline_svg([("main", rows, "red")])
    assert svg.count("<circle") == 2 and "AVX512_VNNI" in svg


def test_page_delta_m(tmp_path):
    """The ΔM scenarios of the repo: each range and its sensitivity across p, beside SCI."""
    from floor import policy
    html = page.build(tmp_path / "none", tmp_path / "out", generated="x",
                      scenarios_dir=policy.PACKAGE_ROOT / "scenarios").read_text(encoding="utf-8")
    assert "<td>x86-64-v1 -&gt; x86-64-v4</td><td><b>889–87,338</b></td>" in html
    assert "<td>30–330</td>" in html and "never added into SCI" in html
    assert "No ΔM scenario yet" in page.build(tmp_path / "none", tmp_path / "o2", generated="x").read_text("utf-8")


def test_page_repairs(tmp_path):
    """The repair loop: one row for each fix MR, with links to GitLab."""
    import json

    from test_repairs import API

    from floor import repairs
    found = repairs.rows(API.__getitem__)
    (tmp_path / "ev" / "repair").mkdir(parents=True)
    (tmp_path / "ev" / "repair" / "repairs.json").write_text(json.dumps(
        {"as_of": "2026-10-21T04:00:00+00:00", "rows": found, "summary": repairs.summary(found)}), encoding="utf-8")
    (tmp_path / "ev" / "repair" / "notes.json").write_text(json.dumps({"notes": {"3": "a <note>"}}), encoding="utf-8")
    html = page.build(tmp_path / "ev", tmp_path / "out", generated="x").read_text(encoding="utf-8")
    assert '<a href="https://gitlab.example/p/-/merge_requests/10">!10</a></td><td>2.1</td>' in html
    assert "2 fix MRs." in html and "From the GitLab API on 2026-10-21" in html
    assert '<td class="mute">a &lt;note&gt;</td>' in html
    assert "Repair loop: no fix MR yet." in page.build(tmp_path / "none", tmp_path / "o2", generated="x").read_text("utf-8")


def test_cli(tmp_path):
    assert main(["page", "--evidence", str(tmp_path), "--out", str(tmp_path / "site")]) == 0
    assert (tmp_path / "site" / "index.html").exists()
