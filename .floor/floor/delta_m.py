"""ΔM calculator (F14.3, §13.3): a consequential scenario reported beside SCI, never inside it.

    ΔM(r) = N_affected(r) × e × p(r) × (Δ(r) / L)

Every input is a range with a source. The result is a range plus a sensitivity table across p.
ΔM is 0 when every floor holds. A scenario is never presented as a measurement (§13.4).
"""

from __future__ import annotations

from pathlib import Path

import yaml

RANGES = ("n_affected", "e_kgco2e", "delta_years", "lifespan_years")
DEFAULT_P = (0.01, 0.02, 0.05)
NOTE = "scenario, not a measurement; reported beside SCI, never inside it"


class ScenarioError(ValueError):
    pass


def load(path: str | Path) -> dict:
    try:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ScenarioError(f"not valid YAML: {exc}") from exc
    if not isinstance(doc, dict):
        raise ScenarioError("not a mapping")
    validate(doc)
    return doc


def validate(doc: dict) -> None:
    problems = []
    for name in RANGES:
        item = doc.get(name)
        if not isinstance(item, dict):
            problems.append(f"{name}: missing")
            continue
        low, high, source = item.get("low"), item.get("high"), str(item.get("source") or "").strip()
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
            problems.append(f"{name}: low and high must be numbers")
        elif not 0 < low <= high:
            problems.append(f"{name}: needs 0 < low <= high")
        if not source or source.startswith("<"):
            problems.append(f"{name}: needs a source")
    p = doc.get("p", list(DEFAULT_P))
    if not p or not all(isinstance(x, (int, float)) and 0 < x <= 1 for x in p):
        problems.append("p: needs shares between 0 and 1")
    if problems:
        raise ScenarioError("; ".join(problems))


def _bounds(doc: dict, p_low: float, p_high: float) -> tuple[float, float]:
    n, e, d, life = (doc[name] for name in RANGES)
    low = n["low"] * e["low"] * p_low * min(d["low"] / life["high"], 1.0)
    high = n["high"] * e["high"] * p_high * min(d["high"] / life["low"], 1.0)
    return low, high


def compute(doc: dict, floors_held: bool = False) -> dict:
    """``floors_held``: every floor held in the release, so ΔM is 0 (§13.3)."""
    validate(doc)
    p = sorted(doc.get("p", list(DEFAULT_P)))
    if floors_held:
        low = high = 0.0
        table = [{"p": x, "low_kgco2e": 0.0, "high_kgco2e": 0.0} for x in p]
    else:
        low, high = _bounds(doc, p[0], p[-1])
        table = [dict(zip(("p", "low_kgco2e", "high_kgco2e"), (x, *map(_round, _bounds(doc, x, x))))) for x in p]
    return {
        "dimension": doc.get("dimension"),
        "change": doc.get("change"),
        "low_kgco2e": _round(low),
        "high_kgco2e": _round(high),
        "sensitivity": table,
        "inputs": {name: doc[name] for name in RANGES} | {"p": p},
        "note": "0 when every floor holds" if floors_held else NOTE,
    }


def _round(value: float) -> float:
    return round(value, 1) if value >= 10 else round(value, 3)


def notice_line(result: dict) -> str:
    """The "ΔM (scenario):" value for a Leave-Behind Notice (§11.2)."""
    i = result["inputs"]
    return (f"{result['low_kgco2e']}–{result['high_kgco2e']} kgCO₂e "
            f"(N {i['n_affected']['low']}–{i['n_affected']['high']}, e {i['e_kgco2e']['low']}–{i['e_kgco2e']['high']} kg, "
            f"p {min(i['p']):.0%}–{max(i['p']):.0%}, Δ {i['delta_years']['low']}–{i['delta_years']['high']} y, "
            f"L {i['lifespan_years']['low']}–{i['lifespan_years']['high']} y)")


def markdown(result: dict) -> str:
    lines = [f"ΔM (scenario): {notice_line(result)}", "", "| p | low kgCO₂e | high kgCO₂e |", "|---|---|---|"]
    lines += [f"| {row['p']:.0%} | {row['low_kgco2e']} | {row['high_kgco2e']} |" for row in result["sensitivity"]]
    lines += ["", "| Input | Low | High | Source |", "|---|---|---|---|"]
    lines += [f"| {name} | {result['inputs'][name]['low']} | {result['inputs'][name]['high']} | "
              f"{result['inputs'][name]['source']} |" for name in RANGES]
    lines += ["", f"Note: {result['note']}."]
    return "\n".join(lines) + "\n"
