"""The Judge (PRD F5.1, F5.2): marks each floor held, lowered, raised or inconclusive.

Only this script sets a floor status (PRD §9.2). Inputs are measurements from the
scanner, the QEMU probe, and the memory and offline jobs; the previous release
and the policy are the references.

- A floor is compared with the previous release. With no previous release, the policy
  is the reference.
- CPU "held" needs a static proof. Dynamic-only evidence gives "held" with
  coverage_limited (F5.1).
- Pareto rule (F5.2): a change is inclusive only if no floor rises on any dimension.
  A raise together with a lowering is a trade-off. Both need a Leave-Behind Notice.
"""

from __future__ import annotations

from .isa.levels import LEVEL_NAMES, level_name, parse_level

LEVEL_BY_NAME = {name: level for level, name in LEVEL_NAMES.items()}

STATUSES = ("held", "lowered", "raised", "inconclusive")
RSS_RISE_PCT = 10  # F7.1: report a peak-RSS rise over 10%


def _compare(current: int, reference: int) -> str:
    if current < reference:
        return "lowered"
    if current > reference:
        return "raised"
    return "held"


def judge_cpu(policy_cpu: dict, static: dict | None = None, probe: dict | None = None,
              previous: str | None = None) -> dict:
    """``static`` is a scan summary (`floor scan --json` "summary"); ``probe`` is `floor probe` output;
    ``previous`` is the CPU floor of the previous release (for example "x86-64-v3")."""
    limit = parse_level(policy_cpu["x86_64_min_level"])
    notes: list[str] = []
    static_level = None
    if static is not None:
        if static.get("files", {}).get("errors"):
            notes.append(f"scan errors in {len(static['files']['errors'])} file(s)")
        else:
            # "none" = no instruction above the base set was found: the build runs on any x86-64 CPU
            static_level = max(1, LEVEL_BY_NAME[static["floor"]["level"]])

    runs = [run for run in (probe or {}).get("runs", []) if run["result"] in ("pass", "fail")]
    skipped = [run["cpu"] for run in (probe or {}).get("runs", []) if run["result"] == "inconclusive"]
    if skipped:
        notes.append(f"controls failed on {', '.join(skipped)}: those runs do not count")

    level, proof, coverage_limited = None, None, False
    if static_level is not None:
        level, proof = static_level, "static"
        crashed = [run["cpu"] for run in runs if run["result"] == "fail" and parse_level(run["cpu_level"]) >= level]
        if crashed:
            notes.append(f"static floor {level_name(level)}, but the run failed on {', '.join(crashed)}")
            return _cpu_result("inconclusive", level, proof, limit, notes, runs, coverage_limited)
        passed_below = [run["cpu"] for run in runs if run["result"] == "pass" and parse_level(run["cpu_level"]) < level]
        if passed_below:
            notes.append(f"passed below the static floor on {', '.join(passed_below)}; the static floor stands")
    elif runs:
        passing = [parse_level(run["cpu_level"]) for run in runs if run["result"] == "pass"]
        if not passing:
            notes.append("no static proof and no CPU model passed")
            return _cpu_result("inconclusive", None, "dynamic", limit, notes, runs, coverage_limited)
        level, proof, coverage_limited = min(passing), "dynamic", True
    else:
        notes.append("no static scan and no conclusive runs")
        return _cpu_result("inconclusive", None, None, limit, notes, runs, coverage_limited)

    reference = parse_level(previous) if previous else limit
    status = _compare(level, reference)
    if proof == "dynamic" and status == "lowered":
        status = "held"  # dynamic-only evidence cannot prove a lowering
    return _cpu_result(status, level, proof, limit, notes, runs, coverage_limited)


def _cpu_result(status, level, proof, limit, notes, runs, coverage_limited) -> dict:
    return {
        "status": status,
        "x86_64": level_name(level) if level else None,
        "proof": proof,
        "coverage_limited": coverage_limited,
        "meets_policy": None if level is None else level <= limit,
        "policy": level_name(limit),
        "dispatch": {run["cpu"]: run.get("loaded_variant") for run in runs},
        "notes": notes,
    }


def judge_memory(policy_mb: dict, current: dict | None, previous: dict | None = None,
                 peak_rss: dict | None = None, previous_peak_rss: dict | None = None) -> dict | None:
    """``current`` and ``previous`` map model -> smallest passing memory limit in MB. None = unmeasured.
    ``peak_rss`` and ``previous_peak_rss`` map model -> peak RSS in MB. A peak-RSS rise over
    RSS_RISE_PCT goes into the notes. It does not change the status (F7.1)."""
    if not current:
        return None
    statuses, failures = [], []
    for model, value in current.items():
        limit = (policy_mb or {}).get(model)
        if value is None:
            statuses.append("inconclusive")
            continue
        if limit is not None and value > limit:
            failures.append(f"{model}: {value} MB > policy {limit} MB")
        reference = (previous or {}).get(model) or limit
        statuses.append(_compare(value, reference) if reference is not None else "held")
    rises = []
    for model, value in sorted((peak_rss or {}).items()):
        old = (previous_peak_rss or {}).get(model)
        if value is not None and old and value * 100 > old * (100 + RSS_RISE_PCT):
            rises.append(f"{model}: peak RSS {value} MB, {100 * (value - old) / old:.1f}% more than "
                         f"{old} MB in the previous release (report only)")
    return {"status": _worst(statuses), "smallest_passing_mb": current, "peak_rss_mb": peak_rss,
            "meets_policy": not failures, "notes": failures + rises}


def judge_connectivity(policy: dict, current: dict | None, previous: dict | None = None) -> dict | None:
    """``current``: `floor offline` output, at least {"offline": bool, "network_attempts": int}.
    The download sizes ("download_mb", "download_bytes") are copied as they are. None = unmeasured."""
    if current is None:
        return None
    offline = bool(current.get("offline")) and not current.get("network_attempts")
    was_offline = None if previous is None else bool(previous.get("offline"))
    if was_offline is None:
        status = "held" if offline or not policy.get("offline_required") else "raised"
    elif was_offline and not offline:
        status = "raised"
    elif offline and not was_offline:
        status = "lowered"
    else:
        status = "held"
    meets = offline or not policy.get("offline_required")
    return {"status": status, "offline": "proven" if offline else "not proven",
            "network_attempts": current.get("network_attempts"), "download_mb": current.get("download_mb"),
            "download_bytes": current.get("download_bytes"), "meets_policy": meets,
            "notes": [] if meets else ["the policy needs offline use"]}


def _worst(statuses: list[str]) -> str:
    if "inconclusive" in statuses:
        return "inconclusive"
    if "raised" in statuses and "lowered" in statuses:
        return "raised"  # a mixed result inside one dimension is still a raise for that dimension
    for status in ("raised", "lowered"):
        if status in statuses:
            return status
    return "held"


def pareto(floors: dict) -> str:
    """held, inclusive (something lowered, nothing raised), raised, trade-off or inconclusive."""
    statuses = {floor["status"] for floor in floors.values()}
    raised, lowered = "raised" in statuses, "lowered" in statuses
    if raised and lowered:
        return "trade-off"
    if raised:
        return "raised"
    if "inconclusive" in statuses:
        return "inconclusive"
    return "inclusive" if lowered else "held"


def decide(floors: dict, notices: list[str] | None = None) -> dict:
    """The gate decision. ``notices`` lists the dimensions that have a merged Leave-Behind Notice."""
    notices = set(notices or [])
    outcome = pareto(floors)
    reasons = []
    needs_notice = sorted(d for d, f in floors.items() if f["status"] == "raised" or f.get("meets_policy") is False)
    missing = [d for d in needs_notice if d not in notices]
    for d, f in sorted(floors.items()):
        if f["status"] == "inconclusive":
            reasons.append(f"{d}: inconclusive")
        if f["status"] == "raised":
            reasons.append(f"{d}: raised")
        if f.get("meets_policy") is False:
            reasons.append(f"{d}: below the policy floor")
    if any(f["status"] == "inconclusive" for f in floors.values()) or missing:
        decision = "fail"
    elif needs_notice:
        decision = "pass-with-notice"
    else:
        decision = "pass"
    return {"decision": decision, "pareto": outcome, "needs_notice": needs_notice,
            "missing_notice": missing, "reasons": reasons}


def judge(policy: dict, *, scan: dict | None = None, probe: dict | None = None, memory: dict | None = None,
          peak_rss: dict | None = None, connectivity: dict | None = None, previous: dict | None = None,
          notices: list[str] | None = None) -> dict:
    """Judges one release. ``previous`` is the "floors" object of the previous manifest."""
    previous = previous or {}
    floors = {"cpu": judge_cpu(policy["cpu"], scan, probe, (previous.get("cpu") or {}).get("x86_64"))}
    previous_memory = previous.get("memory") or {}
    mem = judge_memory(policy.get("memory_mb") or {}, memory, previous_memory.get("smallest_passing_mb"),
                       peak_rss, previous_memory.get("peak_rss_mb"))
    if mem is not None:
        floors["memory"] = mem
    conn = judge_connectivity(policy.get("connectivity") or {}, connectivity,
                              None if "connectivity" not in previous else
                              {"offline": previous["connectivity"].get("offline") == "proven"})
    if conn is not None:
        floors["connectivity"] = conn
    unmeasured = [d for d in ("memory", "connectivity") if d not in floors]
    return {"floors": floors, "unmeasured": unmeasured, **decide(floors, notices)}
