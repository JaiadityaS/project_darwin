"""The Floor page (F12.2): one static HTML file built only from evidence files.

The hero: the floors of the latest judged release. Then nine sections: the H-1 verdict (with the same-commit pairs
and this project's own GitLab runners), the backtest timeline, the CPU proof under QEMU, the repair loop on GitLab,
the languages, the energy per audio-minute of each build, SCI, the ΔM scenarios and the notices.
A section with no evidence says "not measured yet".
No external requests: the fonts and the sprites of Mochi the cat are files next to index.html (folder assets/).
One small inline script moves Mochi and filters the language table. Without it, every table is complete.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from html import escape
from pathlib import Path

from . import delta_m, repairs, runners

LEVELS = ("x86-64-v1", "x86-64-v2", "x86-64-v3", "x86-64-v4")
SERIES = (("main", "main-", "var(--teal)"), ("main-cuda", "main-cuda-", "var(--ink)"))
BUILDS = ("native", "folk-fix", "all-variants", "x64-only")
UNITS = {"audio-minutes": "audio-minute", "release-checks": "release check"}
ASSETS = Path(__file__).with_name("page_assets")

FONTS = "".join(
    f"@font-face{{font-family:'Ubuntu Mono';font-style:{style};font-weight:{weight};font-display:swap;"
    f"src:url(assets/UbuntuMono-{name}.woff2) format('woff2')}}"
    for name, style, weight in (("Regular", "normal", 400), ("Bold", "normal", 700),
                                ("Italic", "italic", 400), ("BoldItalic", "italic", 700)))

CSS = FONTS + """
:root{color-scheme:light;--ink:#0a0a0a;--paper:#fff;--teal:#0f7f76;--teal-soft:#e9f5f2;--line:#c9e4df;
--s1:8px;--s2:16px;--s3:24px;--s4:40px;--s5:64px;--s6:96px;--wrap:1200px;--gutter:32px;
--t-display:clamp(36px,4.4vw,60px);--t-h2:clamp(24px,2.4vw,30px);--t-num:56px;--t-stat:clamp(40px,5vw,64px);
--t-lede:18px;--t-body:17px;--t-table:16px;--t-note:15px}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:'Ubuntu Mono',ui-monospace,Consolas,monospace;
font-size:var(--t-body);line-height:1.55}
a{color:var(--teal);text-underline-offset:3px}a:hover{color:var(--ink)}
a:focus-visible,button:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
code{font-family:inherit;font-size:1em}p{margin:0}
.wrap{max-width:var(--wrap);margin:0 auto;padding:0 var(--gutter)}
.bar{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 24px;padding-top:14px;padding-bottom:14px;font-size:16px}
header{border-bottom:2px solid var(--teal)}
h1{display:inline;margin:0;font-size:1em;color:var(--teal);text-transform:lowercase}
.hero{padding-top:var(--s6);padding-bottom:var(--s5);display:flex;flex-direction:column;gap:var(--s5)}
.hero-row{display:flex;flex-wrap:wrap;gap:var(--s4) var(--s5);align-items:flex-end}
.hero-text{flex:1.4 1 480px;min-width:0;display:flex;flex-direction:column;gap:var(--s3)}
.display{font-size:var(--t-display);line-height:1.06;font-weight:700;max-width:18ch}
.hl{color:var(--teal)}
.hero-side{flex:1 1 340px;min-width:0;display:flex;flex-direction:column}
.release{border:1px solid var(--teal);border-top-width:3px;padding:var(--s3);display:flex;flex-direction:column;gap:var(--s2)}
.release dl{margin:0;display:grid;grid-template-columns:auto minmax(0,1fr) auto;gap:10px var(--s2);font-size:var(--t-table)}
.release dd{margin:0}
.release .foot{border-top:1px dashed var(--teal);padding-top:var(--s2);font-size:var(--t-note)}
.toc{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:0 var(--s4)}
.toc li{border-top:1px solid var(--ink)}
.toc a{display:flex;gap:var(--s2);align-items:baseline;min-height:44px;padding:10px 0;color:var(--ink);text-decoration:none}
.toc a span{color:var(--teal);font-weight:700}.toc a:hover{color:var(--teal)}
.sec{display:flex;flex-wrap:wrap;gap:var(--s4) var(--s5);padding:var(--s5) 0;border-top:2px solid var(--teal)}
.side{flex:1 1 300px;max-width:420px;display:flex;flex-direction:column;gap:var(--s2)}
.body{flex:2.4 1 560px;min-width:0;display:flex;flex-direction:column;gap:var(--s3)}
.num{font-size:var(--t-num);line-height:1;font-weight:700;color:var(--teal)}
h2{margin:0;font-size:var(--t-h2);line-height:1.15;font-weight:700}
h3{margin:0;font-size:var(--t-body);font-weight:700;color:var(--teal)}
.lede{font-size:var(--t-lede);line-height:1.5}
.src{font-size:var(--t-note);font-style:italic;line-height:1.5}
.mute{color:#4a5a58}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:var(--t-table);line-height:1.45}
th{text-align:left;font-weight:700;color:var(--teal);padding:10px 20px 10px 0;border-bottom:2px solid var(--teal);white-space:nowrap}
td{padding:8px 20px 8px 0;border-bottom:1px dashed var(--ink);vertical-align:top;white-space:nowrap}
tr:last-child td{border-bottom:1px solid var(--ink)}
td.note{min-width:320px;white-space:normal;font-size:var(--t-note)}
.fail{font-weight:700;text-decoration:underline wavy var(--teal) 1.5px;text-underline-offset:4px}
.inc{font-style:italic}
.stats{display:flex;flex-wrap:wrap;gap:var(--s3) var(--s5)}
.stats>div{flex:1 1 240px;display:flex;flex-direction:column;gap:4px}
.stat{font-size:var(--t-stat);line-height:1;font-weight:700;color:var(--teal)}
figure{margin:0;border:1px solid var(--teal);padding:var(--s2)}
figcaption{display:flex;flex-wrap:wrap;gap:4px var(--s3);margin-top:8px;font-size:var(--t-note)}
.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px}
svg text{fill:var(--teal);font-family:inherit;font-size:13px}
pre{white-space:pre-wrap;font-family:inherit;margin:0}
.filters{display:flex;flex-wrap:wrap;gap:var(--s2) var(--s4);align-items:center}
.filters>div{display:flex;align-items:center;flex-wrap:wrap}.filters>div>span{margin-right:12px}
.fbtn{font:inherit;font-size:var(--t-table);background:var(--paper);color:var(--teal);border:1px solid var(--teal);
margin-left:-1px;min-height:44px;padding:0 var(--s2);cursor:pointer}
.fbtn:hover{background:var(--teal-soft)}
.fbtn.on{background:var(--teal-soft);font-weight:700;box-shadow:inset 0 -3px 0 var(--teal)}
.mochi{position:relative;align-self:flex-end;margin:0 var(--s3) -4px 0;width:200px;height:200px;border:0;padding:0;
background:none;cursor:pointer;overflow:visible}
.mochi:focus-visible{outline:2px solid var(--teal);outline-offset:4px}
.mochi .sprite{position:absolute;inset:0;transform-origin:50% 100%}
.mochi img{position:absolute;inset:0;width:100%;height:100%;image-rendering:pixelated;pointer-events:none}
.mochi .jump{animation:mjump .65s ease-out}
@keyframes mjump{0%{transform:scale(1.08,.88)}12%{transform:translateY(0) scale(.96,1.06)}
50%{transform:translateY(-64px) scale(.96,1.06)}88%{transform:translateY(0) scale(1,1)}94%{transform:scale(1.07,.9)}100%{transform:none}}
.mochi .tail,.mochi .head{position:absolute;inset:0;background-repeat:no-repeat;image-rendering:pixelated}
.mochi .tail{background-image:url(assets/mochi-tail.svg);background-size:3200px 200px;animation:mtail 2.6s steps(16) infinite}
.mochi:hover .tail,.mochi.petting .tail{animation-duration:1s}
.mochi.sleeping .tail{animation-duration:7.8s}
@keyframes mtail{from{background-position:0 0}to{background-position:-3200px 0}}
.mochi .head{--open:-1600px;background-image:url(assets/mochi-head.svg);background-size:2600px 200px;
background-position:var(--open) 0;animation:mblink 6s step-end infinite}
@keyframes mblink{0%{background-position:var(--open) 0}30%{background-position:-200px 0}32.5%{background-position:var(--open) 0}
70%{background-position:-400px 0}74.5%{background-position:var(--open) 0}90%{background-position:-200px 0}
92.5%{background-position:var(--open) 0}100%{background-position:var(--open) 0}}
.mochi:hover .head,.mochi.petting .head{background-position:-600px 0;animation:mnod .44s step-end infinite}
.mochi.sleeping .head{background-position:-200px 0;animation:mnod 1.4s step-end infinite}
@keyframes mnod{0%{transform:none}50%{transform:translateY(4px)}100%{transform:none}}
.mochi .p{position:absolute;top:24px;pointer-events:none;font-weight:700;font-size:20px;color:var(--teal);animation:mrise 1.6s ease-out forwards}
.mochi .p.heart{width:14px;height:14px;background:var(--teal);clip-path:polygon(50% 100%,0 45%,0 15%,20% 0,50% 18%,80% 0,100% 15%,100% 45%)}
.mochi .p.z{color:var(--ink);animation-duration:2.4s}
@keyframes mrise{0%{opacity:0;transform:translate(0,0) scale(.6)}15%{opacity:1}100%{opacity:0;transform:translate(14px,-84px) scale(1.1)}}
@media (prefers-reduced-motion:reduce){.mochi *{animation:none!important}}
footer{margin-top:var(--s5);border-top:2px solid var(--teal)}
footer .bar{padding-top:var(--s4);padding-bottom:var(--s4);font-size:var(--t-note)}
@media (max-width:600px){:root{--gutter:16px;--s5:40px;--s6:56px}}
"""

# Mochi: the eyes follow the pointer, a pet gives hearts and a purr, a click makes her jump, and after 12 s with
# no movement she sleeps. The language filter shows the rows of one model or one served value.
JS = """(function(){
var m=document.getElementById("mochi"),reduce=window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches;
if(m){var head=m.querySelector(".head"),sprite=m.querySelector(".sprite"),last=Date.now(),pet=false,sleep=false,
jumping=false,lastHeart=0,lastPrr=0,lastZ=0,eye=8;
function fx(kind,txt){if(reduce)return;var p=document.createElement("span");p.className="p "+kind;
p.setAttribute("aria-hidden","true");p.textContent=txt;p.style.left=Math.round((kind=="z"?150:110)+Math.random()*60)+"px";
m.appendChild(p);setTimeout(function(){p.remove();},kind=="z"?2400:1600);}
function mood(){m.classList.toggle("petting",pet&&!sleep);m.classList.toggle("sleeping",sleep);}
function wake(e){last=Date.now();
if(e&&typeof e.clientX=="number"){var r=m.getBoundingClientRect(),sc=r.width/200||1,
dx=(e.clientX-(r.left+146*sc))/(4*sc),dy=(e.clientY-(r.top+62*sc))/(4*sc),
ex=Math.abs(dx)>6?(dx>0?1:-1):0,ey=dy<-8?-1:dy>10?1:0,i=4+(ey+1)*3+(ex+1);
if(i!=eye){eye=i;head.style.setProperty("--open",(-200*i)+"px");}}
if(sleep){sleep=false;mood();}}
function on(){wake();pet=true;mood();}function off(){pet=false;mood();}
document.addEventListener("mousemove",wake,{passive:true});
m.addEventListener("mouseenter",on);m.addEventListener("mouseleave",off);
m.addEventListener("focus",on);m.addEventListener("blur",off);
m.addEventListener("click",function(){wake();if(jumping)return;jumping=true;fx("heart","");fx("heart","");fx("heart","");
sprite.classList.add("jump");setTimeout(function(){sprite.classList.remove("jump");jumping=false;},650);});
setInterval(function(){var now=Date.now();
if(!sleep&&!pet&&!jumping&&now-last>12000){sleep=true;mood();}
if(pet&&!sleep&&now-lastHeart>650){lastHeart=now;fx("heart","");}
if(pet&&!sleep&&now-lastPrr>1800){lastPrr=now;fx("prr","prrr");}
if(sleep&&now-lastZ>1400){lastZ=now;fx("z","z");}},100);}
var f=document.getElementById("langfilter");
if(f){var rows=document.querySelectorAll("#langs tbody tr"),state={model:"all",served:"all"};f.hidden=false;
f.addEventListener("click",function(e){var b=e.target.closest("button[data-k]");if(!b)return;state[b.dataset.k]=b.dataset.v;
f.querySelectorAll('button[data-k="'+b.dataset.k+'"]').forEach(function(x){var o=x===b;x.classList.toggle("on",o);
x.setAttribute("aria-pressed",o?"true":"false");});
rows.forEach(function(r){r.hidden=!((state.model=="all"||r.dataset.model==state.model)&&
(state.served=="all"||r.dataset.served==state.served));});});}
})();"""

TITLES = (("s1", "Does the build machine set the floor?"), ("s2", "Backtest: published images over time"),
          ("s3", "CPU proof: three builds, four old CPUs"), ("s4", "The repair loop on GitLab"), ("s5", "Languages"),
          ("s6", "Energy per audio-minute: the cost of inclusion"), ("s7", "Footprint (SCI)"),
          ("s8", "ΔM: the devices that a floor raise could throw away"), ("s9", "Leave-Behind Notices"))


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


def _table(head: list[str], rows: str, attrs: str = "") -> str:
    return (f'<div class="scroll"><table{attrs}><thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def _stat(value: str, caption: str) -> str:
    return f'<div><span class="stat">{value}</span><span>{caption}</span></div>'


def _verdict(text: str) -> str:
    """'supported: 11 of 38 ...' as '<strong>Supported.</strong> 11 of 38 ...'."""
    word, _, rest = str(text).partition(": ")
    return f'<strong class="hl">{escape(word.capitalize())}.</strong> {escape(rest)}{"." if rest else ""}'


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
                     f'stroke="var(--line)"/><text x="0" y="{y(level, 4):.1f}">{level}</text>')
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


def _link(url: str | None, label: str) -> str:
    return f'<a href="{escape(url)}">{escape(label)}</a>' if url else escape(label)


def _status(value: str | None) -> str:
    cls = {"success": "pass", "failed": "fail"}.get(value or "", "inc")
    return f'<span class="{cls}">{escape(value or "-")}</span>'


# Each section gives (side, body): the side holds the finding and its source; the body holds the tables.

def _section_h1(h1: dict | None, h1_cuda: dict | None, gitlab: dict | None) -> tuple[str, str]:
    side, body = [], []
    if not h1:
        side.append('<p class="lede">H-1: not measured yet.</p>')
    else:
        side.append(f'<p class="lede">{_verdict(h1.get("pair_verdict") or h1.get("verdict"))}</p>'
                    f'<p>The timeline alone is weaker ({escape(str(h1.get("verdict")))}): {h1.get("flips")} floor '
                    f'changes in {h1.get("images")} <code>main</code> images, {h1.get("flips_without_floor_path_changes")} '
                    'of them with no change to the Dockerfile, CMake or ggml CPU code.</p>')
        pairs = h1.get("same_commit_different_floor") or []
        if pairs:
            rows = "".join(f'<tr><td>{escape(p["commit"][:10])}</td><td>{escape(p["a_floor"])}</td>'
                           f'<td>{escape(p["b_floor"])}</td></tr>' for p in pairs)
            body.append('<h3>Same source, two images, two floors</h3>'
                        + _table(["Commit", "<code>main</code>", "<code>main-cuda</code>"], rows))
    side_src, gitlab_body = _h1_gitlab(gitlab)
    return "".join(side) + side_src, "".join(body) + gitlab_body


def _h1_gitlab(doc: dict | None) -> tuple[str, str]:
    """H-1 on this project's own `main` pipelines: the shared runner that built each image and its CPU floor."""
    if not doc or not (doc.get("summary") or {}).get("pipelines"):
        return "", ""
    urls = {r["pipeline"]: r.get("url") for r in doc.get("rows") or []}
    machines = sorted(doc["summary"]["machines"].items(), key=lambda kv: -kv[1]["pipelines"])
    html = [f'<h3>On GitLab too: {doc["summary"]["pipelines"]} <code>main</code> pipelines</h3>'
            f'<p>{escape(runners.text(doc))}</p>',
            _table(["Build machine (shared runner)", "x86-64 level", "<code>main</code> pipelines"],
                   "".join(f'<tr><td>{escape(name)}</td><td>{escape(m["level"])}</td><td>{m["pipelines"]}</td></tr>'
                           for name, m in machines))]
    if doc.get("flips"):
        rows = []
        for f in doc["flips"]:
            ends = [f'{_link(urls.get(e["pipeline"]), str(e["pipeline"]))} {escape(e["sha"][:8])} {escape(e["floor"])}'
                    for e in (f["from"], f["to"])]
            changed = ", ".join(escape(p) for p in f["build_changes"]) or '<span class="fail">none</span>'
            rows.append(f'<tr><td>{ends[0]}</td><td>{ends[1]}</td><td>{f["commits"]}</td><td>{f["changed_files"]}</td>'
                        f'<td>{changed}</td></tr>')
        html.append(_table(["From", "To", "Commits", "Files", "Build inputs changed"], "".join(rows)))
    src = ('<p class="src">Each <code>main</code> pipeline builds the upstream recipe <code>.devops/main.Dockerfile</code> '
           'on a shared runner, until a merged fix MR changes <code>.devops/</code>; the counts stop there. The build job prints the build machine; the judge finds the CPU floor in the image. '
           'Build inputs: the Dockerfiles, the CMake files, the ggml CPU code and <code>.gitlab-ci.yml</code>. From the '
           f'GitLab API and the job logs on {escape(str(doc.get("as_of") or "-")[:10])}.</p>')
    return src, "".join(html)


def _section_timeline(timelines: dict[str, list[dict]], cost: dict | None = None) -> tuple[str, str]:
    series = [(name, timelines[name], colour) for name, _, colour in SERIES if timelines.get(name)]
    if not series:
        return '<p class="lede">Backtest: not measured yet.</p>', ""
    total = sum(len(rows) for _, rows, _ in series)
    raised = sum(1 for _, rows, _ in series for r in rows if r.get("floor") == "x86-64-v4")
    newest = max((r for _, rows, _ in series for r in rows), key=lambda r: r.get("created") or "")
    when = escape(newest["created"][:10])
    tail = (f"including the newest, from {when}" if newest.get("floor") == "x86-64-v4"
            else f"The newest, from {when}, needs {escape(newest['floor'])}")
    side = (f'<p class="lede">Of {total} published images, <span class="fail">{raised} need AVX-512</span> '
            f'(x86-64-v4), {tail}.</p>{_backtest_cost(cost)}')
    legend = "".join(f'<span><i class="dot" style="background:{c}"></i><code>{escape(n)}</code> ({len(r)})</span>'
                     for n, r, c in series)
    body = (f'<figure>{timeline_svg(series)}<figcaption>{legend}</figcaption></figure>'
            '<p class="src">Each dot is one published image. Hover a dot for its tag and its extra instruction sets.</p>')
    return side, body


def _backtest_cost(cost: dict | None) -> str:
    """F14.4: the one-off footprint of the backtest, in bytes and runner time."""
    if not cost:
        return ""
    return (f'<p class="src">The backtest is a one-off cost: the scans downloaded {cost["download_mb"] / 1000:.1f} GB '
            f'(one config and one /app layer per image) in {cost["runner_minutes"]:.0f} runner-minutes '
            f'({len(cost.get("runs", []))} sweep runs).</p>')


def _section_cpu(proofs: list[dict]) -> tuple[str, str]:
    if not proofs:
        return '<p class="lede">CPU proof under QEMU: not measured yet.</p>', ""
    cpus = []
    for proof in proofs:
        for run in proof["probe"].get("runs", []):
            if run["cpu"] not in cpus:
                cpus.append(run["cpu"])
    rows, everywhere = [], []
    for proof in proofs:
        by_cpu = {r["cpu"]: r for r in proof["probe"].get("runs", [])}
        if all(by_cpu.get(c, {}).get("result") == "pass" for c in cpus):
            everywhere.append(proof)
        cells = []
        for cpu in cpus:
            run = by_cpu.get(cpu)
            if not run:
                cells.append("<td>-</td>")
                continue
            cls = {"pass": "pass", "fail": "fail"}.get(run["result"], "inc")
            detail = run.get("signal") or run.get("loaded_variant") or ""
            cells.append(f'<td><span class="{cls}">{escape(run["result"])}</span> {escape(detail)}</td>')
        rows.append(f'<tr><td><b>{escape(proof["config"])}</b></td><td>{escape(proof["floor"])}</td>{"".join(cells)}</tr>')
    if everywhere:
        names = ", ".join(f'<strong class="hl">{escape(p["config"])}</strong>' for p in everywhere)
        lede = f"Only {names} runs on all {len(cpus)} CPUs."
        if any(p["config"] == "all-variants" for p in everywhere):
            floor = next(p["floor"] for p in everywhere if p["config"] == "all-variants")
            lede += f" all-variants picks its CPU code at run time, so its static floor is {escape(floor)}."
    else:
        lede = f"No build runs on all {len(cpus)} CPUs."
    side = (f'<p class="lede">{lede}</p><p class="src">whisper-cli transcribes the JFK sample under QEMU user mode. Each '
            'CPU model also runs a positive control (must pass) and a negative control one level higher (must crash); '
            'a run counts only when both controls behave.</p>')
    return side, _table(["Build", "Static floor", *map(escape, cpus)], "".join(rows))


def _section_repairs(doc: dict | None, notes: dict | None = None) -> tuple[str, str]:
    """F4 on GitLab: each fix MR of the floor-repair flow, its time and its gate."""
    if not doc or not doc.get("rows"):
        return '<p class="lede">Repair loop: no fix MR yet.</p>', ""
    notes = (notes or {}).get("notes", {})
    rows = "".join(
        f'<tr><td>{_link(r.get("failed_url"), str(r["failed_pipeline"]))}</td>'
        f'<td>{_link(r.get("mr_url"), "!" + str(r["mr"]))}</td>'
        f'<td>{"-" if r.get("minutes") is None else format(r["minutes"], ".1f")}</td>'
        f'<td>{_link(r.get("gate_url"), str(r.get("gate_pipeline") or "-"))}</td><td>{_status(r.get("gate_judge"))}</td>'
        f'<td>{_status(r.get("gate_status"))}</td><td>{escape(r.get("state") or "-")}</td>'
        f'<td class="note">{escape(notes.get(str(r["mr"]), ""))}</td></tr>'
        for r in doc["rows"])
    side = (f'<p class="lede">{escape(repairs.text(doc))} A person decides the merge.</p>'
            '<p class="src">The judge (a script) failed the pipeline because a floor rose. The floor-repair flow read the '
            'judge log and the patch of the fallback job, and opened the fix MR. Minutes: from the end of the failed '
            'pipeline to the MR. The MR pipeline runs the same gate again. '
            f'From the GitLab API on {escape((doc.get("as_of") or "?")[:10])}.</p>')
    summary = doc.get("summary") or {}
    stats = "".join(_stat(format(summary[key], ".1f"), caption) for key, caption in
                    (("median_minutes", "median minutes to a fix MR"), ("max_minutes", "slowest, in minutes"))
                    if summary.get(key) is not None)
    body = (f'<div class="stats">{stats}</div>' if stats else "") + _table(
        ["Failed pipeline", "Fix MR", "Minutes", "MR pipeline", "Its judge", "Its status", "MR state", "Note"], rows)
    return side, body


def _release(diff: str | None) -> tuple[str, str]:
    """The hero: one sentence and the floors of the latest judged release, from release/diff.md."""
    question = "Which machines does this release still run on?"
    if not diff:
        return (question, '<div class="release"><b class="hl">This release</b>'
                '<p>Not known: no release judged yet.</p></div>')
    lines = diff.splitlines()
    rows = [[c.strip() for c in line.strip("|").split("|")] for line in lines
            if line.startswith("|") and not line.startswith("|---")][1:]
    floors = {r[0]: r for r in rows if len(r) >= 4}
    title = next((line.lstrip("# ").replace("Floor diff: ", "") for line in lines if line.startswith("#")), "")
    rest = [escape(line.replace("**", "")) for line in lines if line and not line.startswith(("|", "#"))]
    cpu = floors.get("cpu", [""] * 4)[2]
    if cpu == "x86-64-v1":
        sentence = 'Every x86-64 machine back to <span class="hl">v1</span> can still run this release.'
    elif cpu in LEVELS:
        sentence = f'This release needs an x86-64 CPU at <span class="hl">{escape(cpu[-2:])}</span> or newer.'
    else:
        sentence = question
    dl = "".join(f'<dt>{escape(r[0])}</dt><dd>{escape(r[2])}</dd>'
                 f'<dd><span class="{"pass" if r[3] == "held" else "fail"}">{escape(r[3])}</span></dd>'
                 for r in floors.values())
    return sentence, (f'<div class="release"><b class="hl">This release</b><span class="src">{escape(title)}</span>'
                      f'<dl>{dl}</dl><p class="foot">{"<br>".join(rest)}</p></div>')


def _section_languages(doc: dict | None) -> tuple[str, str]:
    if not doc or not doc.get("rows"):
        return ('<p class="lede">Language table: not measured yet.</p><p class="src">The gate checks English only: the '
                'JFK sample must give the expected words. A served / not-served table needs FLEURS runs at f16 and at '
                'one quantization level. Until then, Rieux makes no claim for any other language.</p>'), ""
    usable, quant = doc["usable_wer"], escape(doc.get("quant") or "?")
    rows = []
    for r in doc["rows"]:
        served = '<span class="pass">yes</span>' if r["served_f16"] else '<span class="fail">no</span>'
        if r["served_f16"] != r["served_quant"]:
            served += f' <span class="inc">({"yes" if r["served_quant"] else "no"} at {quant})</span>'
        lo, hi = r["drift_ci"]
        rows.append(f'<tr data-model="{escape(r["size"])}" data-served="{"yes" if r["served_f16"] else "no"}">'
                    f'<td>{escape(r["name"])}</td><td>{escape(r["size"])}</td>'
                    f'<td>{r["wer_f16"]:.1%}</td><td>{r["cer_f16"]:.1%}</td><td>{r["wer_quant"]:.1%}</td>'
                    f'<td>{r["drift"] * 100:+.1f} <span class="mute">[{lo * 100:+.1f}, {hi * 100:+.1f}]</span></td>'
                    f'<td>{served}</td></tr>')
    missing = sum(r.get("missing", 0) for r in doc["rows"])
    bad = sum(r.get("bad_utf8", 0) for r in doc["rows"])
    clips = sorted({r["clips"] for r in doc["rows"]})
    side = (f'<p class="lede">Served (f16 WER at most {usable:.0%}): '
            f'<strong class="hl">{escape(", ".join(doc["served"]) or "none")}</strong>. '
            f'Not served: {escape(", ".join(doc["not_served"]) or "none")}.</p>'
            f'<p class="src">FLEURS test split, {"/".join(map(str, clips))} sentences per language (one recording each, '
            f'seeded sample), read speech. WER and CER after one simple normalizer (lower case, no punctuation). '
            f'Pinned decoding: <code>{escape(doc.get("decoding") or "?")}</code>, whisper.cpp '
            f'<code>{escape((doc.get("commit") or "?")[:8])}</code>. The drift is the {quant} WER minus the f16 WER, '
            f'with a paired-bootstrap interval. Real speech is noisier than read speech, so real error rates are higher. '
            f'Report only: no gate uses this table (F9.3).'
            + (f' {missing} clip(s) gave no transcript and count as all words wrong.' if missing else "")
            + (f' {bad} transcript(s) had bytes that are not UTF-8; each broken word counts as wrong.'
               if bad else "")
            + f' Not measured: {len(doc["not_measured"])} other whisper languages, so Rieux makes no '
            f'claim for them.</p>')
    sizes = list(dict.fromkeys(r["size"] for r in doc["rows"]))

    def buttons(key: str, options: list[tuple[str, str]]) -> str:
        return "".join(f'<button type="button" class="fbtn{" on" if v == "all" else ""}" data-k="{key}" '
                       f'data-v="{escape(v)}" aria-pressed="{"true" if v == "all" else "false"}">{escape(label)}</button>'
                       for v, label in options)
    filters = (f'<div class="filters" id="langfilter" hidden>'
               f'<div role="group" aria-label="Filter by model"><span>Model</span>'
               f'{buttons("model", [("all", "all"), *((s, s) for s in sizes)])}</div>'
               f'<div role="group" aria-label="Filter by served"><span>Show</span>'
               f'{buttons("served", [("all", "all"), ("yes", "served"), ("no", "not served")])}</div></div>')
    body = filters + _table(["Language", "Model", "WER f16", "CER f16", f"WER {quant}", "Drift, points (95% CI)",
                             "Served"], "".join(rows), ' id="langs"')
    return side, body


def _section_energy(energy: dict | None, sci: dict | None) -> tuple[str, str]:
    if not energy or not energy.get("builds") or not energy.get("audio_minutes"):
        return '<p class="lede">Energy per audio-minute: not measured yet.</p>', ""
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
                        f'{sum(1 for r in runs if not r.get("ok"))} of {len(runs)} runs failed</td></tr>')
            continue
        spread = _spread(build)
        change = _vs(build["cpu_s"], folk["cpu_s"]) if folk.get("cpu_s") and name != "folk-fix" else "-"
        rows.append(f'<tr><td><b>{escape(name)}</b></td><td>{build["cpu_s"] / minutes:.1f}</td>'
                    f'<td>{build["wall_s"] / minutes:.1f}</td><td>{_sig(wh.get(name))}</td>'
                    f'<td>{build["peak_rss_mb"]:.0f}</td><td>{escape(build.get("loaded_variant") or "built in")}</td>'
                    f'<td>{"-" if spread is None else f"{spread:.1%}"}</td><td>{change}</td></tr>')
    notes, stats = [], []
    if "cpu_s" in shipped and folk.get("cpu_s"):
        costs = [f"{_vs(shipped['cpu_s'], folk['cpu_s'])} CPU time"]
        if wh.get("all-variants") and wh.get("folk-fix"):
            costs.append(f"{_vs(wh['all-variants'], wh['folk-fix'])} energy")
        text = (f'<b>The cost of inclusion: {", ".join(costs)} per audio-minute</b>, all-variants against folk-fix on '
                'the same machine. all-variants picks its CPU code at run time (see the CPU proof). folk-fix needs AVX2.')
        caption = "CPU time, all-variants against folk-fix."
        spreads = [s for s in (_spread(shipped), _spread(folk)) if s is not None]
        if spreads:
            inside = abs(shipped["cpu_s"] / folk["cpu_s"] - 1) < max(spreads)
            text += (f' The runs of one build differ by up to {max(spreads):.1%}, so this difference is '
                     f'{"inside" if inside else "outside"} the noise of the measurement.')
            caption += f' {"Inside" if inside else "Outside"} the {max(spreads):.1%} run-to-run noise.'
        notes.append(f'<p class="lede">{text}</p>')
        stats.append(_stat(_vs(shipped["cpu_s"], folk["cpu_s"]), caption))
    if "cpu_s" in oldest and "cpu_s" in shipped:
        ratio = f'{oldest["cpu_s"] / shipped["cpu_s"]:.1f}×'
        notes.append(f'<p>x64-only, the CPU code that ggml loads on an x86-64-v1 CPU, needs {ratio} the CPU time of '
                     'all-variants on this machine.</p>')
        stats.append(_stat(ratio, "CPU time of x64-only, the code that ggml loads on an x86-64-v1 CPU, "
                                  "against all-variants."))
    side = ("".join(notes) + '<p class="src">native: built for the CPU of the build machine. folk-fix: '
            '<code>GGML_NATIVE=OFF</code>. all-variants: every CPU variant, chosen at run time. x64-only: the '
            'all-variants build with only its lowest variant, x64. Spread of runs: (highest - lowest) CPU time of the '
            f'runs, as a part of the median. Each run transcribes {minutes} audio-minutes. Median of '
            f'{energy.get("runs_per_build")} runs per build. The builds take turns on one machine '
            f'({escape(str(energy.get("cpu_model")))}, {energy.get("vcpus")} vCPUs). CPU time is user plus system time '
            'from GNU time.</p>')
    body = (f'<div class="stats">{"".join(stats)}</div>' if stats else "") + _table(
        ["Build", "CPU s per audio-minute", "Wall s per audio-minute", "Wh per audio-minute", "Peak RSS (MB)",
         "CPU backend", "Spread of runs", "CPU time vs folk-fix"], "".join(rows))
    return side, body


def _section_sci(sci: dict | None) -> tuple[str, str]:
    if not sci or not sci.get("rows"):
        return '<p class="lede">SCI: not measured yet.</p>', ""
    regions = sci.get("regions") or {}
    stats = "".join(_stat(_sig(value), f'g CO2e per {UNITS[unit]} ({escape(str(regions.get(unit, "-")))})')
                    for unit, value in (("audio-minutes", sci.get("sci_gco2e_per_audio_minute")),
                                        ("release-checks", sci.get("sci_gco2e_per_release_check")))
                    if value is not None)
    rows = "".join(f'<tr><td>{escape(UNITS.get(r["unit"], r["unit"]))}</td>'
                   f'<td>{escape(r["child"])}{" (headline)" if r["headline"] else ""}</td>'
                   f'<td>{escape(str(r["region"] or "-"))}</td><td>{_sig(r["grid_gco2e_per_kwh"])}</td>'
                   f'<td>{_sig(None if r["energy_kwh"] is None else r["energy_kwh"] * 1000)}</td>'
                   f'<td>{_sig(r["carbon_gco2e"])}</td><td>{_sig(r["sci_gco2e"])}</td></tr>' for r in sci["rows"])
    side = ('<p class="lede">Per audio-minute and per release check. The grid intensity is location-based, with no '
            f'offsets.</p><p class="src">SCI = (E × I + M) / R (ISO/IEC 21031:2024), computed by '
            f'{escape(str(sci.get("method")))}. Energy and carbon are for one measured run. SCI divides them by the '
            'units of that run.</p>')
    body = f'<div class="stats">{stats}</div>' + _table(
        ["Unit", "Case", "Region", "Grid (g CO2e per kWh)", "Energy (Wh)", "Carbon (g CO2e)", "SCI (g CO2e per unit)"],
        rows)
    return side, body


def _section_delta_m(scenarios: dict[str, dict] | None) -> tuple[str, str]:
    """§13.3: each scenario with its range and its sensitivity across p. Beside SCI, never inside it."""
    side = ('<p class="lede">A scenario, not a measurement. It is never added into SCI.</p>'
            '<p class="src">ΔM = N × e × p × (Δ / L): the embodied carbon of the devices that a floor raise could force '
            'people to replace. N: devices below the new floor, as each file states it (the CPU files count per 10,000 '
            'x86 users, a unit, not a count of real users). e: the embodied carbon of a replacement device. p: the '
            'share of affected people who replace their device. Δ / L: the part of the device life that is cut '
            'short.</p>')
    if not scenarios:
        return '<p class="lede">No ΔM scenario yet.</p>', ""
    shares = sorted({row["p"] for result in scenarios.values() for row in result["sensitivity"]})
    rows = ""
    for name, result in sorted(scenarios.items()):
        by_p = {row["p"]: row for row in result["sensitivity"]}
        cells = "".join(f'<td>{_kg(by_p[p]["low_kgco2e"])}–{_kg(by_p[p]["high_kgco2e"])}</td>' if p in by_p
                        else "<td>-</td>" for p in shares)
        rows += (f'<tr><td>{escape(str(result["change"]))}</td><td><b>{_kg(result["low_kgco2e"])}–'
                 f'{_kg(result["high_kgco2e"])}</b></td>{cells}<td><code>.floor/scenarios/{escape(name)}</code></td></tr>')
    return side, _table(["Floor change", "ΔM (kg CO2e)", *(f"p = {p:.0%}" for p in shares), "Inputs and sources"], rows)


def _kg(value: float) -> str:
    """Whole kilograms; one decimal below 10 kg, so that a small scenario does not round to 0 or 1."""
    return f"{value:,.1f}" if value < 10 else f"{value:,.0f}"


def _section_notices(notices: dict[str, str], drafts: dict | None = None) -> tuple[str, str]:
    """F6: the accepted notices, then each draft of the notice-draft job (F4.5) and what a code owner did with it."""
    rows = (drafts or {}).get("drafts") or []
    if notices:
        lede = f'{len(notices)} accepted notice(s).'
        body = "".join(f'<h3>{escape(name)}</h3><pre>{escape(text)}</pre>' for name, text in sorted(notices.items()))
    else:
        lede = '<strong class="hl">None.</strong> No Leave-Behind Notices. No release has left anyone behind.'
        body = ""
    if rows:
        refused = sum(1 for d in rows if d.get("decision") == "refused")
        lede += f" {len(rows)} draft(s) written, {refused} refused."
    side = (f'<p class="lede">{lede}</p><p class="src">The notice-draft job writes a draft only when the fix and the '
            'canned config did not hold a floor. Only a code owner decides. To accept the raise, the owner adds the '
            'notice in a new MR and approves it. To refuse it, the owner closes the MR, and the raise does not '
            'ship. Agents and the merge-bot cannot approve a notice.</p>')
    if rows:
        body += _table(["MR", "Floor change", "ΔM (kg CO2e)", "Draft (pipeline)", "Decision", "Date", "Note"], "".join(
            f'<tr><td>{_link(d.get("mr_url"), "!" + str(d["mr"]))}</td><td>{escape(d.get("change") or "-")}</td>'
            f'<td>{_kg_range(d.get("delta_m_kgco2e"))}</td><td>{_link(d.get("job_url"), str(d.get("pipeline") or "-"))}</td>'
            f'<td><b>{escape(d.get("decision") or "open")}</b></td><td>{escape((d.get("decided_at") or "-")[:10])}</td>'
            f'<td class="note">{escape(d.get("note") or "")}</td></tr>' for d in rows))
    return side, body


def _kg_range(pair: list | None) -> str:
    return f"{_kg(pair[0])}–{_kg(pair[1])}" if pair and len(pair) == 2 else "-"


def collect(evidence: Path, notices_dir: Path | None = None, scenarios_dir: Path | None = None) -> dict:
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
    scenarios = {}
    for path in sorted(scenarios_dir.glob("*.yml")) if scenarios_dir and scenarios_dir.is_dir() else []:
        if path.name != "TEMPLATE.yml":
            try:
                scenarios[path.name] = delta_m.compute(delta_m.load(path))
            except (OSError, delta_m.ScenarioError):
                continue
    costs = sorted((evidence / "backtest").glob("footprint-*.json")) if (evidence / "backtest").is_dir() else []
    return {"timelines": timelines, "h1": h1, "h1_cuda": h1_cuda, "proofs": proofs, "diff": diff, "notices": notices,
            "backtest_cost": _load(costs[-1]) if costs else None,
            "language": _load(evidence / "language" / "language.json"),
            "energy": _load(evidence / "energy" / "energy.json"), "sci": _load(evidence / "footprint" / "sci.json"),
            "delta_m": scenarios, "repairs": _load(evidence / "repair" / "repairs.json"),
            "runners": _load(evidence / "runners" / "runners.json"),
            "repair_notes": _load(evidence / "repair" / "notes.json"),
            "notice_drafts": _load(evidence / "notice" / "drafts.json")}


def render(data: dict, generated: str) -> str:
    sections = (_section_h1(data["h1"], data["h1_cuda"], data.get("runners")),
                _section_timeline(data["timelines"], data.get("backtest_cost")),
                _section_cpu(data["proofs"]),
                _section_repairs(data.get("repairs"), data.get("repair_notes")),
                _section_languages(data.get("language")),
                _section_energy(data["energy"], data["sci"]),
                _section_sci(data["sci"]),
                _section_delta_m(data.get("delta_m")),
                _section_notices(data["notices"], data.get("notice_drafts")))
    body = "".join(f'<section id="{sid}" class="sec"><div class="side"><span class="num">{n:02d}</span>'
                   f'<h2>{escape(title)}</h2>{side}</div><div class="body">{main}</div></section>'
                   for n, ((sid, title), (side, main)) in enumerate(zip(TITLES, sections), 1))
    toc = "".join(f'<li><a href="#{sid}"><span>{n:02d}</span> {escape(title)}</a></li>'
                  for n, (sid, title) in enumerate(TITLES, 1))
    sentence, release = _release(data["diff"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rieux</title><meta name="description" content="Who each whisper.cpp release serves: CPU, memory and offline floors, with proof.">
<link rel="preload" href="assets/UbuntuMono-Regular.woff2" as="font" type="font/woff2" crossorigin>
<style>{CSS}</style></head><body>
<header><div class="wrap bar"><div><h1>Rieux</h1>: a hardware-floor report for whisper.cpp</div></div></header>
<main>
<section id="top" class="wrap hero"><div class="hero-row"><div class="hero-text">
<p class="display">{sentence}</p>
<p class="lede">Every release of whisper.cpp says which machines it still runs on, with proof. If a change would leave
people behind, the gate stops it, an agent repairs it, and only a human can accept the loss.</p></div>
<div class="hero-side"><button type="button" class="mochi" id="mochi" title="Pet me, or click"
aria-label="Mochi the cat. Hover to pet her, click to make her jump."><span class="sprite"><span class="tail"></span>
<img src="assets/mochi-body.svg" alt="" width="200" height="200"><span class="head"></span></span></button>
{release}</div></div>
<nav aria-label="Contents"><ol class="toc">{toc}</ol></nav></section>
<div class="wrap">{body}</div>
</main>
<footer><div class="wrap bar"><span style="max-width:70ch">Built from the evidence files in <code>.floor/evidence/</code>
on {escape(generated)}. <code>.floor/evidence/backtest/README.md</code> gives the job of each file and the commands to
make it again. Font: Ubuntu Mono (<a href="assets/UFL.txt">Ubuntu Font Licence</a>).</span>
<a href="#top">Back to top ↑</a></div></footer>
<script>{JS}</script>
</body></html>
"""


def build(evidence: str | Path, out: str | Path, notices_dir: str | Path | None = None,
          generated: str | None = None, scenarios_dir: str | Path | None = None) -> Path:
    data = collect(Path(evidence), Path(notices_dir) if notices_dir else None,
                   Path(scenarios_dir) if scenarios_dir else None)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ASSETS, out / "assets", dirs_exist_ok=True)
    target = out / "index.html"
    target.write_text(render(data, generated or datetime.now().strftime("%Y-%m-%d")), encoding="utf-8", newline="\n")
    return target
