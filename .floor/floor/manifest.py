"""Floor Manifest (PRD F5.3, §11.1): an in-toto Statement and a diff against the previous release.

The Judge sets every status. This module only copies the Judge output into the manifest
and compares two manifests. Signing (F5.4, `cosign attest`) happens in CI on the result.
"""

from __future__ import annotations

import os

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_VERSION = "v0.3"
ALWAYS_UNMEASURED = ("arm64", "gpu-backends")
_CPU_FIELDS = ("x86_64", "status", "proof", "coverage_limited", "dispatch", "meets_policy", "policy", "notes")


def predicate_type(project_url: str | None = None) -> str:
    url = (project_url or os.environ.get("CI_PROJECT_URL") or "").rstrip("/")
    return f"{url}/floor-manifest/{PREDICATE_VERSION}" if url else f"urn:floor:floor-manifest:{PREDICATE_VERSION}"


def _floors(verdict: dict, evidence: str | None) -> dict:
    floors = {}
    for name, floor in verdict["floors"].items():
        kept = {key: value for key, value in floor.items() if name != "cpu" or key in _CPU_FIELDS}
        if evidence:
            kept["evidence"] = evidence
        floors[name] = kept
    return floors


def _value(dimension: str, floor: dict | None):
    if not floor:
        return None
    if dimension == "cpu":
        return floor.get("x86_64")
    if dimension == "memory":
        return floor.get("smallest_passing_mb")
    if dimension == "connectivity":
        return floor.get("offline")
    return floor.get("status")


def changes(previous: dict | None, floors: dict, fixed_by: str | None = None) -> list[dict]:
    """One entry per dimension whose value moved. ``previous`` is the "floors" of the previous manifest."""
    if not previous:
        return []  # the first release: nothing to compare with
    rows = []
    for dimension in sorted(set(previous) | set(floors)):
        old, new = _value(dimension, previous.get(dimension)), _value(dimension, floors.get(dimension))
        if old == new:
            continue
        row = {"dimension": dimension, "from": old, "to": new,
               "status": (floors.get(dimension) or {}).get("status", "unmeasured")}
        if fixed_by and row["status"] == "lowered":
            row["fixed_by"] = fixed_by
        rows.append(row)
    return rows


def build(verdict: dict, *, subject: str, digest: str, release: str, commit: str,
          scan: dict | None = None, cmake_flags: str | None = None, base_image: str | None = None,
          previous: dict | None = None, evidence: str | None = None, fixed_by: str | None = None,
          notices: list[str] | None = None, project_url: str | None = None, delta_m: dict | None = None,
          footprint: dict | None = None) -> dict:
    """``verdict`` is `floor judge` output, ``scan`` a scan summary, ``previous`` the previous manifest,
    ``footprint`` `floor footprint check --out` output."""
    floors = _floors(verdict, evidence)
    previous_predicate = (previous or {}).get("predicate") or {}
    raised = [name for name, floor in floors.items() if floor["status"] == "raised"]
    unmeasured = list(ALWAYS_UNMEASURED) + verdict.get("unmeasured", [])
    if "language" not in floors:
        unmeasured.append("language")
    predicate = {
        "release": release,
        "commit": commit,
        "build": {
            "cmake_flags": cmake_flags,
            "base_image": base_image,
            "source_date_epoch": bool(os.environ.get("SOURCE_DATE_EPOCH")),
            "highest_level_found": (scan or {}).get("highest_level_found"),
            "baseline_variant": (scan or {}).get("baseline_variant"),
        },
        "floors": floors,
        "decision": verdict["decision"],
        "pareto": verdict["pareto"],
        "unmeasured": unmeasured,
        "diff_from": previous_predicate.get("release"),
        "changes": changes(previous_predicate.get("floors"), floors, fixed_by),
        "leave_behind_notices": list(notices or []),
        "footprint": {"sci_gco2e_per_audio_minute": (footprint or {}).get("sci_gco2e_per_audio_minute"),
                      "sci_gco2e_per_release_check": (footprint or {}).get("sci_gco2e_per_release_check"),
                      "method": (footprint or {}).get("method", "GSF Impact Framework")},
        "delta_m_kgco2e": _delta_m(raised, delta_m),
    }
    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": subject, "digest": {"sha256": digest.removeprefix("sha256:")}}],
        "predicateType": predicate_type(project_url),
        "predicate": predicate,
    }


def _delta_m(raised: list[str], scenario: dict | None) -> dict:
    """``scenario`` is `floor delta-m` output. ΔM stays beside SCI, never inside it (§13.3)."""
    if not raised:
        return {"low": 0, "high": 0, "note": "0 when every floor holds"}
    if scenario:
        return {"low": scenario["low_kgco2e"], "high": scenario["high_kgco2e"], "note": scenario["note"]}
    return {"low": None, "high": None, "note": "set by the Leave-Behind Notice scenario"}


def _cell(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, dict):
        return ", ".join(f"{k} {v}" for k, v in value.items())
    return str(value)


def diff_markdown(old: dict | None, new: dict) -> str:
    """A readable diff of two manifests (AC-F5). ``old`` may be None for the first release."""
    old_p, new_p = (old or {}).get("predicate") or {}, new["predicate"]
    old_floors, new_floors = old_p.get("floors") or {}, new_p["floors"]
    lines = [f"## Floor diff: {old_p.get('release') or 'no previous release'} → {new_p['release']}", "",
             "| Floor | Previous | This release | Status |", "|---|---|---|---|"]
    for dimension in sorted(set(old_floors) | set(new_floors)):
        floor = new_floors.get(dimension) or {}
        status = floor.get("status", "unmeasured")
        if floor.get("coverage_limited"):
            status += " (coverage-limited)"
        lines.append(f"| {dimension} | {_cell(_value(dimension, old_floors.get(dimension)))} | "
                     f"{_cell(_value(dimension, floor))} | {status} |")
    lines += ["", f"Pareto: **{new_p['pareto']}**. Gate decision: **{new_p['decision']}**."]
    if new_p["changes"]:
        lines += ["", "Changes:"] + [f"- {c['dimension']}: {_cell(c['from'])} → {_cell(c['to'])} ({c['status']})"
                                     for c in new_p["changes"]]
    else:
        lines += ["", "No floor moved."]
    lines += ["", f"Not measured: {', '.join(new_p['unmeasured'])}."]
    return "\n".join(lines) + "\n"
