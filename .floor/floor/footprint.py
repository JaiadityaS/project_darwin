"""SCI (PRD F14.1, §13.1): SCI = (E × I + M) / R, computed with Impact Framework manifests.

`write` turns the measured evidence into Impact Framework (IF) manifests, `.floor/impact/sci-*.yml`.
CI runs `if-run` on them. `check` then recomputes every IF output from its own inputs with
`expected`, so a wrong pipeline or a changed number fails. The published SCI values come from the
IF outputs. The coefficients and their sources are in `.floor/impact/footprint.yml`.

E follows the Cloud Carbon Footprint (CCF) method: per vCPU, idle watts for the reserved time plus
(max - idle) watts for the busy CPU time, plus watts per GB of memory, times the PUE of the data
centre. M is the time share and the vCPU share of the embodied emissions of the host.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import yaml

from .policy import PACKAGE_ROOT

IMPACT_DIR = PACKAGE_ROOT / "impact"
DEFAULT_CONFIG = IMPACT_DIR / "footprint.yml"
ENERGY_FILE = PACKAGE_ROOT / "evidence" / "energy" / "energy.json"
METER_FILE = PACKAGE_ROOT / "evidence" / "release" / "meter.json"
SUMMARY_FILE = PACKAGE_ROOT / "evidence" / "footprint" / "sci.json"
IF_PACKAGE = "@grnsft/if@1.1.1"
METHOD = f"GSF Impact Framework ({IF_PACKAGE}, if-run) with Cloud Carbon Footprint coefficients"
SHIPPED = "all-variants"  # the build that a held release ships
HEADLINE = {"audio-minutes": SHIPPED, "release-checks": "release-check"}
FILES = {"audio-minutes": "sci-audio-minute.yml", "release-checks": "sci-release-check.yml"}
INPUTS = ("duration", "cpu/vcpus", "cpu/busy-seconds", "memory/gb-seconds", "cpu/watts-min", "cpu/watts-max",
          "memory/watts-per-gb", "pue", "grid/carbon-intensity", "host/vcpus")
HEADER = ("# Made by `python -m floor footprint write` from {source}.\n"
          "# Do not edit. Change the evidence or .floor/impact/footprint.yml, then run the command again.\n"
          "# CI runs if-run ({package}) on this file and checks every output (PRD F14.1).\n")

# CPU model name -> CCF microarchitecture. A CPU that is not here gets the provider average.
_ARCH = (
    (r"EPYC\s+7\w\w2\b", "EPYC 2nd Gen"),
    (r"EPYC\s+7\w\w3\b", "EPYC 3rd Gen"),
    (r"EPYC\s+9\w\w4\b", "EPYC 4th Gen"),
    (r"Xeon.*\b[3-9]1\d\d", "Skylake"),
    (r"Xeon.*\b[3-9]2\d\d", "Cascade Lake"),
    (r"Xeon.*\b[3-9]3\d\d", "Ice Lake"),
    (r"Xeon.*\b[3-9]4\d\d", "Sapphire Rapids"),
    (r"Xeon.*\b[3-9]5\d\d", "Emerald Rapids"),
    (r"Xeon.*E5-\d{4}\w* v4", "Broadwell"),
)


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data) -> bool:  # write every value in full, never as an anchor
        return True


def load(path: str | Path = DEFAULT_CONFIG) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def microarchitecture(cpu_model: str | None) -> str | None:
    for pattern, name in _ARCH:
        if cpu_model and re.search(pattern, cpu_model, re.IGNORECASE):  # GCP VMs write "INTEL(R) XEON(R) ..."
            return name
    return None


def watts_for(config: dict, cpu_model: str | None, provider: str) -> tuple[dict, str]:
    """The CCF watts of one vCPU for this CPU, or the provider average when the CPU is not known."""
    arch = microarchitecture(cpu_model)
    rows = config["watts_per_vcpu"]["microarchitecture"]
    if arch in rows:
        return {"min": rows[arch]["min"], "max": rows[arch]["max"]}, f"{arch} (CCF {rows[arch]['table']} table)"
    row = config["watts_per_vcpu"]["provider"][provider]
    return {"min": row["min"], "max": row["max"]}, f"{provider} average (CCF)"


def energy_wh(vcpu_s: float, cpu_s: float, memory_gb_s: float, watts: dict, memory_watts_per_gb: float,
              pue: float) -> float:
    """CCF: average watts = min + utilisation × (max - min) per vCPU, so idle watts × vCPU-seconds
    plus (max - min) × busy CPU seconds. Then memory, then the PUE."""
    joules = vcpu_s * watts["min"] + cpu_s * (watts["max"] - watts["min"]) + memory_gb_s * memory_watts_per_gb
    return joules * pue / 3600


def _op(method: str, config: dict) -> dict:
    return {"method": method, "path": "builtin", "config": config}


def _product(inputs: list[str], output: str) -> dict:
    return _op("Multiply", {"input-parameters": inputs, "output-parameter": output})


def plugins(host: dict, lifespan_s: int, unit: str) -> dict:
    """The IF pipeline, in order. ``host`` is one entry of embodied.hosts in footprint.yml."""
    return {
        "vcpu-seconds": _product(["cpu/vcpus", "duration"], "cpu/vcpu-seconds"),
        "watts-delta": _op("Subtract", {"input-parameters": ["cpu/watts-max", "cpu/watts-min"],
                                        "output-parameter": "cpu/watts-delta"}),
        "cpu-idle": _product(["cpu/vcpu-seconds", "cpu/watts-min"], "cpu/idle-joules"),
        "cpu-load": _product(["cpu/busy-seconds", "cpu/watts-delta"], "cpu/load-joules"),
        "memory": _product(["memory/gb-seconds", "memory/watts-per-gb"], "memory/joules"),
        "it-energy": _op("Sum", {"input-parameters": ["cpu/idle-joules", "cpu/load-joules", "memory/joules"],
                                 "output-parameter": "it/joules"}),
        "facility-energy": _product(["it/joules", "pue"], "facility/joules"),
        "energy-kwh": _op("Divide", {"numerator": "facility/joules", "denominator": 3600000, "output": "energy"}),
        "operational-carbon": _product(["energy", "grid/carbon-intensity"], "carbon-operational"),
        "host-share": _op("Divide", {"numerator": "cpu/vcpus", "denominator": "host/vcpus", "output": "usage-ratio"}),
        "embodied-carbon": _op("SciEmbodied", {"baseline-emissions": round(host["total_kgco2e"] * 1000, 3),
                                               "lifespan": lifespan_s}),
        "carbon": _op("Sum", {"input-parameters": ["carbon-operational", "embodied-carbon"],
                              "output-parameter": "carbon"}),
        "sci": _op("Sci", {"functional-unit": unit}),
    }


def site_defaults(config: dict, site: str, region: str | None = None) -> dict:
    """The coefficients of one site (sites in footprint.yml), as IF defaults."""
    entry = config["sites"][site]
    provider, region = entry["provider"], region or entry["region"]
    watts = config["watts_per_vcpu"]["provider"][provider]
    return {
        "cloud/provider": provider,
        "cloud/region": region,
        "cpu/watts-min": watts["min"],
        "cpu/watts-max": watts["max"],
        "memory/watts-per-gb": config["memory_watts_per_gb"]["value"],
        "pue": config["pue"][provider],
        "grid/carbon-intensity": config["grid_intensity"][region],
        "host/vcpus": config["embodied"]["hosts"][entry["host"]]["vcpus"],
    }


def audio_inputs(energy: dict) -> dict[str, dict]:
    """One IF input per build: its median transcription of the audio file (`floor energy` output)."""
    found = {}
    for name, build in energy["builds"].items():
        if "wall_s" not in build:
            continue
        found[name] = {"timestamp": energy["measured_at"], "duration": build["wall_s"], "cpu/vcpus": energy["vcpus"],
                       "cpu/busy-seconds": build["cpu_s"],
                       "memory/gb-seconds": round(build["peak_rss_mb"] / 1024 * build["wall_s"], 3),
                       "audio-minutes": energy["audio_minutes"]}
    return found


def release_inputs(meter: dict) -> dict:
    """The IF input of one release check (`floor meter stop` output)."""
    return {"timestamp": meter["measured_at"], "duration": meter["wall_s"], "cpu/vcpus": meter["vcpus"],
            "cpu/busy-seconds": meter["cpu_s"], "memory/gb-seconds": meter["memory_gb_s"], "release-checks": 1}


def _manifest(config: dict, unit: str, site: str, children: dict[str, tuple[dict, dict]], description: str) -> dict:
    host = config["embodied"]["hosts"][config["sites"][site]["host"]]
    steps = plugins(host, config["embodied"]["lifespan_s"], unit)
    return {
        "name": f"floor-sci-{unit[:-1]}",
        "description": description,
        "tags": {"kind": "sci", "category": unit},
        "initialize": {"plugins": steps},
        "tree": {"children": {name: {"pipeline": {"compute": list(steps)}, "defaults": defaults, "inputs": [obs]}
                              for name, (defaults, obs) in children.items()}},
    }


def _dump(doc: dict, source: str | None) -> str:
    body = yaml.dump(doc, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110)
    return HEADER.format(source=source or "local evidence", package=IF_PACKAGE) + body


def write(config: dict, energy: dict | None = None, meter: dict | None = None) -> dict[str, str]:
    """The IF manifests that the evidence gives, as {file name: YAML}. No evidence, no manifest."""
    files = {}
    if energy:
        service = config["sites"]["service"]
        children = {name: (site_defaults(config, "service"), obs) for name, obs in audio_inputs(energy).items()}
        compare = service.get("compare_region")
        if compare and SHIPPED in children:
            children[f"{SHIPPED}-{compare}"] = (site_defaults(config, "service", compare), dict(children[SHIPPED][1]))
        description = (
            f"SCI per audio-minute (R1) for each whisper.cpp build. CPU time: `floor energy` on a GitHub-hosted "
            f"runner ({energy.get('cpu_model')}, {energy['vcpus']} vCPUs), median of {energy['runs_per_build']} runs. "
            f"Site: Cloud Run in {service['region']} (F13.1). Cloud Run does not publish its CPU platform, so the "
            f"GCP average watts and an {service['host']} host are assumptions. The '{SHIPPED}' child is the shipped "
            f"build; '{SHIPPED}-{compare}' is the same work in {compare} (PRD §13.2, lever 5).")
        files[FILES["audio-minutes"]] = _dump(_manifest(config, "audio-minutes", "service", children, description),
                                              energy.get("evidence"))
    if meter:
        site = config["sites"]["release-check"]
        defaults = site_defaults(config, "release-check")
        # The meter ran on the release-check site itself, so the CPU that it saw gives the watts (D-015).
        watts, label = watts_for(config, meter.get("cpu_model"), site["provider"])
        defaults.update({"cpu/watts-min": watts["min"], "cpu/watts-max": watts["max"]})
        jobs = meter.get("jobs") or {}
        what = f"the sum of {len(jobs)} jobs ({', '.join(jobs)})" if jobs else "one job"
        scope = "the cgroup of each job container" if meter.get("scope") == "cgroup" else "the whole machine"
        description = (
            f"SCI per release check (R2): every Floor probe of one release. CPU time and memory: `floor meter` "
            f"({scope}), {what}, on {meter.get('cpu_model') or 'more than one CPU model'} with {meter['vcpus']} "
            f"vCPUs. Watts: {label}. "
            f"Site: a GitLab-hosted runner in {site['region']}. The {site['host']} host is an assumption. "
            f"No repair agent ran, so agent tokens add 0.")
        children = {"release-check": (defaults, release_inputs(meter))}
        files[FILES["release-checks"]] = _dump(_manifest(config, "release-checks", "release-check", children,
                                                         description), meter.get("evidence"))
    return files


def stale(files: dict[str, str], folder: Path) -> list[str]:
    """Differences between the manifests that the evidence gives and the files in ``folder``."""
    found = []
    on_disk = {path.name for path in Path(folder).glob("sci-*.yml")}
    for name, text in sorted(files.items()):
        path = Path(folder) / name
        if not path.exists():
            found.append(f"{path}: missing")
        elif path.read_text(encoding="utf-8") != text:
            found.append(f"{path}: not what the evidence gives")
    found += [f"{Path(folder) / name}: no evidence for it" for name in sorted(on_disk - set(files))]
    return found


def _num(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def expected(obs: dict, embodied_g: float, lifespan_s: float, unit: str) -> dict:
    """SCI from the raw inputs with the CCF formulas: a check of the IF pipeline that does not use it."""
    n = {key: _num(obs.get(key)) for key in INPUTS + (unit,)}
    missing = [key for key, value in n.items() if value is None]
    if missing:
        raise ValueError(f"missing input {', '.join(missing)}")
    watts = {"min": n["cpu/watts-min"], "max": n["cpu/watts-max"]}
    energy = energy_wh(n["cpu/vcpus"] * n["duration"], n["cpu/busy-seconds"], n["memory/gb-seconds"], watts,
                       n["memory/watts-per-gb"], n["pue"]) / 1000
    operational = energy * n["grid/carbon-intensity"]
    embodied = embodied_g * n["cpu/vcpus"] / n["host/vcpus"] * n["duration"] / lifespan_s
    carbon = operational + embodied
    return {"energy": energy, "carbon-operational": operational, "embodied-carbon": embodied, "carbon": carbon,
            "sci": carbon / n[unit] if n[unit] else carbon}


def _leaves(node: dict, prefix: str = ""):
    for name, child in (node.get("children") or {}).items():
        if child.get("children"):
            yield from _leaves(child, f"{prefix}{name}/")
        else:
            yield f"{prefix}{name}", child


def check(doc: dict, source: str = "") -> tuple[list[dict], list[str]]:
    """Recomputes every output of one if-run output file. Returns the SCI rows and the problems."""
    rows, problems = [], []
    execution = doc.get("execution") or {}
    if execution.get("status") not in (None, "success"):
        problems.append(f"{source}: if-run status {execution.get('status')}: {execution.get('error')}")
    methods = {p.get("method"): p.get("config") or {} for p in ((doc.get("initialize") or {}).get("plugins") or {}).values()}
    if "SciEmbodied" not in methods or "Sci" not in methods:
        return rows, problems + [f"{source}: the pipeline needs SciEmbodied and Sci"]
    embodied, unit = methods["SciEmbodied"], methods["Sci"].get("functional-unit")
    embodied_g = _num(embodied.get("baseline-emissions", 1000000))
    lifespan_s = _num(embodied.get("lifespan", 126144000))
    for child, node in _leaves(doc.get("tree") or {}):
        outputs = node.get("outputs") or []
        if not outputs:
            problems.append(f"{source}: {child}: no outputs (run if-run first)")
        for out in outputs:
            try:
                want = expected(out, embodied_g, lifespan_s, unit)
            except ValueError as exc:
                problems.append(f"{source}: {child}: {exc}")
                continue
            for key, value in want.items():
                got = _num(out.get(key))
                if got is None or not math.isclose(got, value, rel_tol=1e-9, abs_tol=1e-12):
                    problems.append(f"{source}: {child}: {key} is {out.get(key)}, the formula gives {value:.6g}")
            rows.append({"manifest": doc.get("name"), "child": child, "unit": unit, "headline": child == HEADLINE.get(unit),
                         "region": out.get("cloud/region"), "grid_gco2e_per_kwh": _num(out.get("grid/carbon-intensity")),
                         "energy_kwh": _num(out.get("energy")), "operational_gco2e": _num(out.get("carbon-operational")),
                         "embodied_gco2e": _num(out.get("embodied-carbon")), "carbon_gco2e": _num(out.get("carbon")),
                         "functional_units": _num(out.get(unit)), "sci_gco2e": _num(out.get("sci"))})
    return rows, problems


def check_file(path: str | Path) -> tuple[list[dict], list[str]]:
    return check(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}, source=str(path))


def summarize(rows: list[dict]) -> dict:
    head = {row["unit"]: row for row in rows if row["headline"]}
    return {
        "method": METHOD,
        "sci_gco2e_per_audio_minute": head["audio-minutes"]["sci_gco2e"] if "audio-minutes" in head else None,
        "sci_gco2e_per_release_check": head["release-checks"]["sci_gco2e"] if "release-checks" in head else None,
        "regions": {unit: row["region"] for unit, row in head.items()},
        "rows": rows,
    }


def differences(new: dict, old: dict | None) -> list[str]:
    """Where the if-run results differ from a committed summary (`floor footprint check --out`)."""
    if not old:
        return ["no committed SCI summary to compare with"]
    a = {(r["manifest"], r["child"]): r for r in new["rows"]}
    b = {(r["manifest"], r["child"]): r for r in old.get("rows", [])}
    found = [f"{m}/{c}: not in the committed summary" for m, c in sorted(a.keys() - b.keys())]
    found += [f"{m}/{c}: in the committed summary, not in the if-run outputs" for m, c in sorted(b.keys() - a.keys())]
    for key in sorted(a.keys() & b.keys()):
        for field in ("energy_kwh", "carbon_gco2e", "sci_gco2e"):
            x, y = a[key][field], b[key][field]
            if x is None or y is None or not math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-12):
                found.append(f"{key[0]}/{key[1]}: {field} is {x}, the committed summary has {y}")
    return found
