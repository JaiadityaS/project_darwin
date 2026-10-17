"""The Floor page (PRD F12.2): one static HTML file built only from evidence files.

Sections: the H-1 verdict, the backtest timeline, same-commit pairs, the CPU proof under QEMU,
the latest manifest diff, the languages, the energy per audio-minute of each build, SCI, and the
notices. A section with no evidence says "not measured yet".
No scripts, no external requests: the page works offline, like the product it describes.
"""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

LEVELS = ("x86-64-v1", "x86-64-v2", "x86-64-v3", "x86-64-v4")
SERIES = (("main", "main-", "var(--a)"), ("main-cuda", "main-cuda-", "var(--b)"))
BUILDS = ("native", "folk-fix", "all-variants", "x64-only")
UNITS = {"audio-minutes": "audio-minute", "release-checks": "release check"}

CSS = """
:root{color-scheme:light dark;--bg:#fbfaf7;--fg:#1d1d1b;--mute:#6b6a64;--line:#dedbd2;--card:#fff;--a:#1f6feb;--b:#d9480f;
--ok:#2b8a3e;--bad:#c92a2a;--warn:#b26b00;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--fg:#ecebe6;--mute:#a3a198;--line:#34332f;--card:#1c1c1a;
--a:#6ea8fe;--b:#ff8a50;--ok:#69db7c;--bad:#ff8787;--warn:#ffc078}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);line-height:1.5}
main{max-width:980px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:2rem;margin:0 0 8px;letter-spacing:-.01em}h2{font-size:1.25rem;margin:40px 0 8px}
p{margin:8px 0}.mute{color:var(--mute)}.lead{font-size:1.1rem;max-width:62ch}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0;overflow-x:auto}
.verdict{border-left:4px solid var(--warn)}.verdict.ok{border-left-color:var(--ok)}
table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
td:first-child{white-space:nowrap}
th{color:var(--mute);font-weight:600}code{font-family:ui-monospace,Consolas,monospace;font-size:.88em}
.pass{color:var(--ok);font-weight:600}.fail{color:var(--bad);font-weight:600}.inc{color:var(--warn);font-weight:600}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.stat b{display:block;font-size:1.6rem}.legend span{display:inline-block;margin-right:16px}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}
svg text{fill:var(--mute);font-size:11px}footer{margin-top:48px;font-size:.85rem;color:var(--mute)}
"""


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _date(text: str) -> datetime:
    return datetime.fromisoformat(text[:19])


def _short(ref: str) -> str:
    return ref.rsplit("-", 1)[-1][:8]


def _sig(value) -> str:
    return "-" if value is None else f"{value:.3g}"


def _build_key(name: str) -> tuple[int, str]:
    return (BUILDS.index(name) if name in BUILDS else len(BUILDS), name)


def _spread(build: dict) -> float | None:
    """(highest - lowest) CPU time of the counted runs of one build, as a part of its median: the noise."""
    cpu = [run["cpu_s"] for run in build.get("runs", []) if run.get("ok") and "cpu_s" in run]
    return (max(cpu) - min(cpu)) / build["cpu_s"] if len(cpu) > 1 and build.get("cpu_s") else None


def _vs(value: float, base: float) -> str:
    ratio = value / base
    return f"{ratio:.1f}×" if ratio >= 2 else f"{ratio - 1:+.1%}"


def timeline_svg(series: list[tuple[str, list[dict], str]], width: int = 940, height: int = 220) -> str:
    """Dots per image: x = image date, y = floor level. One row of dots per series."""
    points = [row for _, rows, _ in series for row in rows if row.get("created") and row.get("floor") in LEVELS]
    if not points:
        return ""
    start = min(_date(r["created"]) for r in points)
    end = max(_date(r["created"]) for r in points)
    span = max((end - start).total_seconds(), 1)
    left, right, top, bottom = 80, 16, 16, 40
    levels = [lvl for lvl in LEVELS if any(r["floor"] == lvl for r in points)] or list(LEVELS)
    lo, hi = LEVELS.index(levels[0]), LEVELS.index(levels[-1])
    rows = max(hi - lo, 1)

    def y(level: str, offset: float) -> float:
        return top + (hi - LEVELS.index(level)) * (height - top - bottom) / rows + offset

    def x(created: str) -> float:
        return left + (_date(created) - start).total_seconds() / span * (width - left - right)

    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="Floor of each image over time">']
    for i in range(lo, hi + 1):
        level = LEVELS[i]
        parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y(level, 0):.1f}" y2="{y(level, 0):.1f}" '
                     f'stroke="var(--line)"/><text x="8" y="{y(level, 4):.1f}">{level}</text>')
    for n, (name, rows_, colour) in enumerate(series):
        offset = (n - (len(series) - 1) / 2) * 8
        for row in rows_:
            if row.get("floor") not in LEVELS or not row.get("created"):
                continue
            label = escape(f"{row['ref']} · {row['created'][:10]} · {row['floor']} {' '.join(row.get('extras') or [])}")
            parts.append(f'<circle cx="{x(row["created"]):.1f}" cy="{y(row["floor"], offset):.1f}" r="4" '
                         f'fill="{colour}" fill-opacity=".8"><title>{label}</title></circle>')
    for when, anchor in ((start, "start"), (end, "end")):
        parts.append(f'<text x="{x(when.isoformat()):.1f}" y="{height - 12}" text-anchor="{anchor}">{when:%Y-%m-%d}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _section_h1(h1: dict | None, h1_cuda: dict | None) -> str:
    if not h1:
        return '<div class="card">H-1: not measured yet.</div>'
    pairs = h1.get("same_commit_different_floor") or []
    verdict = h1.get("pair_verdict") or h1.get("verdict")
    ok = str(verdict).startswith("supported")
    headline = "H-1: the build machine sets the floor." if ok else "H-1: not shown yet."
    html = [f'<div class="card verdict{" ok" if ok else ""}"><b>{headline}</b>'
            f'<p>{escape(str(verdict))}.</p>'
            f'<p class="mute">Timeline only: {escape(str(h1.get("verdict")))}. '
            f'{h1.get("flips")} floor changes in {h1.get("images")} <code>main</code> images; '
            f'{h1.get("flips_without_floor_path_changes")} of them with no change to the Dockerfile, CMake or ggml CPU code.</p></div>']
    if pairs:
        html.append('<div class="card"><table><tr><th>Commit</th><th><code>main</code> image</th>'
                    '<th><code>main-cuda</code> image</th></tr>')
        for p in pairs:
            html.append(f'<tr><td><code>{escape(p["commit"][:10])}</code></td><td>{escape(p["a_floor"])}</td>'
                        f'<td>{escape(p["b_floor"])}</td></tr>')
        html.append('</table><p class="mute">Same source, two images, two floors.</p></div>')
    return "".join(html)


def _section_timeline(timelines: dict[str, list[dict]]) -> str:
    series = [(name, timelines[name], colour) for name, _, colour in SERIES if timelines.get(name)]
    if not series:
        return '<div class="card">Backtest: not measured yet.</div>'
    total = sum(len(rows) for _, rows, _ in series)
    raised = sum(1 for _, rows, _ in series for r in rows if r.get("floor") == "x86-64-v4")
    legend = "".join(f'<span><i class="dot" style="background:{c}"></i><code>{escape(n)}</code> ({len(r)})</span>'
                     for n, r, c in series)
    newest = max((r for _, rows, _ in series for r in rows), key=lambda r: r.get("created") or "")
    return (f'<div class="stats"><div class="card stat"><b>{total}</b>published images scanned</div>'
            f'<div class="card stat"><b>{raised}</b>need AVX-512 (x86-64-v4)</div>'
            f'<div class="card stat"><b>{escape(newest["floor"])}</b>newest image, {escape(newest["created"][:10])}</div></div>'
            f'<div class="card"><p class="legend">{legend}</p>{timeline_svg(series)}'
            f'<p class="mute">Each dot is one published image. Hover for the tag and the extra instruction sets.</p></div>')


def _section_cpu(proofs: list[dict]) -> str:
    if not proofs:
        return '<div class="card">CPU proof under QEMU: not measured yet.</div>'
    cpus = []
    for proof in proofs:
        for run in proof["probe"].get("runs", []):
            if run["cpu"] not in cpus:
                cpus.append(run["cpu"])
    head = "".join(f"<th>{escape(c)}</th>" for c in cpus)
    rows = []
    for proof in proofs:
        by_cpu = {r["cpu"]: r for r in proof["probe"].get("runs", [])}
        cells = []
        for cpu in cpus:
            run = by_cpu.get(cpu)
            if not run:
                cells.append("<td>-</td>")
                continue
            cls = {"pass": "pass", "fail": "fail"}.get(run["result"], "inc")
            detail = run.get("signal") or run.get("loaded_variant") or ""
            cells.append(f'<td><span class="{cls}">{escape(run["result"])}</span> '
                         f'<span class="mute">{escape(detail)}</span></td>')
        rows.append(f'<tr><td><b>{escape(proof["config"])}</b></td><td>{escape(proof["floor"])}</td>{"".join(cells)}</tr>')
    return (f'<div class="card"><table><tr><th>Build</th><th>Static floor</th>{head}</tr>{"".join(rows)}</table>'
            '<p class="mute">whisper-cli transcribes the JFK sample under QEMU user mode. Each CPU model also runs '
            'a positive control (must pass) and a negative control one level higher (must crash); a run counts only '
            'when both controls behave.</p></div>')


def _section_manifest(diff: str | None) -> str:
    if not diff:
        return '<div class="card">Release manifest: no release judged yet.</div>'
    lines = [line for line in diff.splitlines() if line.startswith("|") and not line.startswith("|---")]
    table = "".join("<tr>" + "".join(f"<td>{escape(c.strip())}</td>" for c in line.strip("|").split("|")) + "</tr>"
                    for line in lines)
    rest = [escape(line.replace("**", "")) for line in diff.splitlines() if line and not line.startswith(("|", "#"))]
    return f'<div class="card"><table>{table}</table><p>{"<br>".join(rest)}</p></div>'


def _section_languages() -> str:
    return ('<div class="card">Language table: not measured yet. The gate checks English only: the JFK sample must give '
            'the expected words. A served / not-served table needs FLEURS runs at f16 and at one quantization level. '
            'Until then, Rieux makes no claim for any other language.</div>')


def _section_energy(energy: dict | None, sci: dict | None) -> str:
    if not energy or not energy.get("builds") or not energy.get("audio_minutes"):
        return '<div class="card">Energy per audio-minute: not measured yet.</div>'
    minutes, builds = energy["audio_minutes"], energy["builds"]
    # Wh per audio-minute from the if-run results (floor footprint check), when they exist.
    wh = {r["child"]: r["energy_kwh"] * 1000 / r["functional_units"] for r in (sci or {}).get("rows", [])
          if r["unit"] == "audio-minutes" and r["energy_kwh"] is not None and r["functional_units"]}
    shipped, folk, oldest = (builds.get(name, {}) for name in ("all-variants", "folk-fix", "x64-only"))
    rows = []
    for name in sorted(builds, key=_build_key):
        build = builds[name]
        if "cpu_s" not in build:
            runs = build.get("runs", [])
            rows.append(f'<tr><td><b>{escape(name)}</b></td><td colspan="7"><span class="fail">no result</span> '
                        f'<span class="mute">{sum(1 for r in runs if not r.get("ok"))} of {len(runs)} runs failed</span>'
                        '</td></tr>')
            continue
        spread = _spread(build)
        change = _vs(build["cpu_s"], folk["cpu_s"]) if folk.get("cpu_s") and name != "folk-fix" else "-"
        rows.append(f'<tr><td><b>{escape(name)}</b></td><td>{build["cpu_s"] / minutes:.1f}</td>'
                    f'<td>{build["wall_s"] / minutes:.1f}</td><td>{_sig(wh.get(name))}</td>'
                    f'<td>{build["peak_rss_mb"]:.0f}</td><td>{escape(build.get("loaded_variant") or "built in")}</td>'
                    f'<td>{"-" if spread is None else f"{spread:.1%}"}</td><td>{change}</td></tr>')
    notes = []
    if "cpu_s" in shipped and folk.get("cpu_s"):
        costs = [f"{_vs(shipped['cpu_s'], folk['cpu_s'])} CPU time"]
        if wh.get("all-variants") and wh.get("folk-fix"):
            costs.append(f"{_vs(wh['all-variants'], wh['folk-fix'])} energy")
        text = (f'<b>The cost of inclusion: {", ".join(costs)} per audio-minute</b>, all-variants against folk-fix on '
                'the same machine. all-variants picks its CPU code at run time (see the CPU proof). folk-fix needs AVX2.')
        spreads = [s for s in (_spread(shipped), _spread(folk)) if s is not None]
        if spreads:
            inside = abs(shipped["cpu_s"] / folk["cpu_s"] - 1) < max(spreads)
            text += (f' The runs of one build differ by up to {max(spreads):.1%}, so this difference is '
                     f'{"inside" if inside else "outside"} the noise of the measurement.')
        notes.append(f"<p>{text}</p>")
    if "cpu_s" in oldest and "cpu_s" in shipped:
        notes.append(f'<p>x64-only, the CPU code that ggml loads on an x86-64-v1 CPU, needs '
                     f'{oldest["cpu_s"] / shipped["cpu_s"]:.1f}× the CPU time of all-variants on this machine.</p>')
    return (f'<div class="card">{"".join(notes)}<table><tr><th>Build</th><th>CPU s per audio-minute</th>'
            '<th>Wall s per audio-minute</th><th>Wh per audio-minute</th><th>Peak RSS (MB)</th><th>CPU backend</th>'
            f'<th>Spread of runs</th><th>CPU time vs folk-fix</th></tr>{"".join(rows)}</table>'
            '<p class="mute">native: built for the CPU of the build machine. folk-fix: <code>GGML_NATIVE=OFF</code>. '
            'all-variants: every CPU variant, chosen at run time. x64-only: the all-variants build with only its '
            'lowest variant, x64. Spread of runs: (highest - lowest) CPU time of the runs, as a part of the median.</p>'
            f'<p class="mute">Each run transcribes {minutes} audio-minutes. Median of {energy.get("runs_per_build")} runs '
            f'per build. The builds take turns on one machine ({escape(str(energy.get("cpu_model")))}, '
            f'{energy.get("vcpus")} vCPUs). CPU time is user plus system time from GNU time.</p></div>')


def _section_sci(sci: dict | None) -> str:
    if not sci or not sci.get("rows"):
        return '<div class="card">SCI: not measured yet.</div>'
    regions = sci.get("regions") or {}
    stats = "".join(f'<div class="card stat"><b>{_sig(value)}</b>g CO2e per {UNITS[unit]} '
                    f'({escape(str(regions.get(unit, "-")))})</div>'
                    for unit, value in (("audio-minutes", sci.get("sci_gco2e_per_audio_minute")),
                                        ("release-checks", sci.get("sci_gco2e_per_release_check")))
                    if value is not None)
    rows = "".join(f'<tr><td>{escape(UNITS.get(r["unit"], r["unit"]))}</td>'
                   f'<td>{escape(r["child"])}{" (headline)" if r["headline"] else ""}</td>'
                   f'<td>{escape(str(r["region"] or "-"))}</td><td>{_sig(r["grid_gco2e_per_kwh"])}</td>'
                   f'<td>{_sig(None if r["energy_kwh"] is None else r["energy_kwh"] * 1000)}</td>'
                   f'<td>{_sig(r["carbon_gco2e"])}</td><td>{_sig(r["sci_gco2e"])}</td></tr>' for r in sci["rows"])
    return (f'<div class="stats">{stats}</div><div class="card"><table><tr><th>Unit</th><th>Case</th><th>Region</th>'
            '<th>Grid (g CO2e per kWh)</th><th>Energy (Wh)</th><th>Carbon (g CO2e)</th><th>SCI (g CO2e per unit)</th>'
            f'</tr>{rows}</table><p class="mute">SCI = (E × I + M) / R (ISO/IEC 21031:2024), computed by '
            f'{escape(str(sci.get("method")))}. The grid intensity is location-based, with no offsets. Energy and carbon '
            'are for one measured run. SCI divides them by the units of that run.</p></div>')


def _section_notices(notices: dict[str, str]) -> str:
    if not notices:
        return '<div class="card">No Leave-Behind Notices. No release has left anyone behind.</div>'
    return "".join(f'<div class="card"><b>{escape(name)}</b><pre>{escape(text)}</pre></div>'
                   for name, text in sorted(notices.items()))


def collect(evidence: Path, notices_dir: Path | None = None) -> dict:
    backtest = evidence / "backtest"
    timelines, h1, h1_cuda = {}, None, None
    for path in sorted(backtest.glob("*.json")):
        doc = _load(path)
        if not doc:
            continue
        if path.name.startswith("h1-main-cuda"):
            h1_cuda = doc
        elif path.name.startswith("h1-main"):
            h1 = doc
        elif path.name.startswith("main-cuda"):
            timelines["main-cuda"] = doc.get("images", [])
        elif path.name.startswith("main"):
            timelines["main"] = doc.get("images", [])
    proofs = []
    for folder in sorted((evidence / "cpu-proof").glob("*")) if (evidence / "cpu-proof").is_dir() else []:
        probe, scan = _load(folder / "probe.json"), _load(folder / "scan.json")
        if probe:
            proofs.append({"config": probe.get("label") or folder.name, "probe": probe,
                           "floor": (scan or {}).get("summary", {}).get("floor", {}).get("level", "?")})
    proofs.sort(key=lambda p: _build_key(p["config"]))
    diff_path = evidence / "release" / "diff.md"
    diff = diff_path.read_text(encoding="utf-8") if diff_path.exists() else None
    notices = {}
    if notices_dir and notices_dir.is_dir():
        notices = {p.name: p.read_text(encoding="utf-8") for p in sorted(notices_dir.glob("[0-9]*.md"))}
    return {"timelines": timelines, "h1": h1, "h1_cuda": h1_cuda, "proofs": proofs, "diff": diff, "notices": notices,
            "energy": _load(evidence / "energy" / "energy.json"), "sci": _load(evidence / "footprint" / "sci.json")}


def render(data: dict, generated: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rieux</title><meta name="description" content="Who each whisper.cpp release serves: CPU, memory and offline floors, with proof.">
<style>{CSS}</style></head><body><main>
<h1>Rieux</h1>
<p class="lead">Every release of whisper.cpp says which machines it still runs on, with proof. If a change would leave
people behind, the gate stops it, an agent repairs it, and only a human can accept the loss.</p>
<h2>Does the build machine set the floor?</h2>{_section_h1(data["h1"], data["h1_cuda"])}
<h2>Backtest: published images over time</h2>{_section_timeline(data["timelines"])}
<h2>CPU proof: three builds, four old CPUs</h2>{_section_cpu(data["proofs"])}
<h2>Latest release</h2>{_section_manifest(data["diff"])}
<h2>Languages</h2>{_section_languages()}
<h2>Energy per audio-minute: the cost of inclusion</h2>{_section_energy(data["energy"], data["sci"])}
<h2>Footprint (SCI)</h2>{_section_sci(data["sci"])}
<h2>Leave-Behind Notices</h2>{_section_notices(data["notices"])}
<footer>Built from the evidence files in <code>.floor/evidence/</code> on {escape(generated)}.
<code>.floor/evidence/backtest/README.md</code> gives the job of each file and the commands to make it again.</footer>
</main></body></html>
"""


def build(evidence: str | Path, out: str | Path, notices_dir: str | Path | None = None,
          generated: str | None = None) -> Path:
    data = collect(Path(evidence), Path(notices_dir) if notices_dir else None)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    target = out / "index.html"
    target.write_text(render(data, generated or datetime.now().strftime("%Y-%m-%d")), encoding="utf-8", newline="\n")
    return target
