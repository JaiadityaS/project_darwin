"""The repair loop on GitLab (F4): each failed pipeline that the floor-repair flow answered with a fix MR.

The rows come from the GitLab API. A public project needs no token. For each fix MR (branch "floor-fix/<pipeline id>"):
the failed pipeline and its judge, the minutes from the end of that pipeline to the MR, and the gate of the MR (its
latest pipeline and that pipeline's judge). The Floor page shows the result (F12.2).
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Callable

import requests

BRANCH = "floor-fix/"


def _time(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None


def minutes(start: str | None, end: str | None) -> float | None:
    """The minutes from one API time stamp to another, to 0.1 min. None when one is missing."""
    a, b = _time(start), _time(end)
    return round((b - a).total_seconds() / 60, 1) if a and b else None


def judge_status(jobs: list[dict]) -> str | None:
    """The status of the judge job of a pipeline (its latest run). None when the pipeline has no judge job."""
    found = [j for j in jobs if j.get("name") == "judge"]
    return max(found, key=lambda j: j["id"])["status"] if found else None


def rows(get: Callable[[str], list | dict]) -> list[dict]:
    """One row for each fix MR, by MR number. `get(path)` gives the JSON of a GET on the project API."""
    found = []
    for mr in sorted(get("merge_requests?state=all&per_page=100"), key=lambda m: m["iid"]):
        branch = mr.get("source_branch") or ""
        pipeline_id = branch[len(BRANCH):]
        if not branch.startswith(BRANCH) or not pipeline_id.isdigit():
            continue
        failed = get(f"pipelines/{pipeline_id}")
        gates = get(f"merge_requests/{mr['iid']}/pipelines")
        gate = max(gates, key=lambda p: p["id"]) if gates else None
        found.append({
            "mr": mr["iid"], "mr_url": mr["web_url"], "state": mr["state"], "opened_at": mr["created_at"],
            "failed_pipeline": failed["id"], "failed_url": failed.get("web_url"), "failed_ref": failed.get("ref"),
            "failed_at": failed.get("finished_at"),
            "failed_judge": judge_status(get(f"pipelines/{failed['id']}/jobs?per_page=100")),
            "minutes": minutes(failed.get("finished_at"), mr["created_at"]),
            "gate_pipeline": gate["id"] if gate else None, "gate_url": gate.get("web_url") if gate else None,
            "gate_status": gate["status"] if gate else None,
            "gate_judge": judge_status(get(f"pipelines/{gate['id']}/jobs?per_page=100")) if gate else None,
        })
    return found


def summary(found: list[dict]) -> dict:
    """The counts that the page and the CLI print."""
    times = sorted(r["minutes"] for r in found if r["minutes"] is not None)
    return {"fix_mrs": len(found), "under_3_min": sum(t < 3 for t in times),
            "median_minutes": round(statistics.median(times), 1) if times else None,
            "max_minutes": times[-1] if times else None,
            "gate_judge_passed": sum(r["gate_judge"] == "success" for r in found),
            "merged": sum(r["state"] == "merged" for r in found)}


def collect(api_url: str, project_id: str, session: requests.Session | None = None, timeout: float = 30) -> dict:
    """The rows and the counts, read from the API now."""
    http = session or requests.Session()

    def get(path: str):
        response = http.get(f"{api_url}/projects/{project_id}/{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()

    found = rows(get)
    return {"project": str(project_id), "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rows": found, "summary": summary(found)}


def text(doc: dict) -> str:
    """One line of counts, for the CLI and the page."""
    s = doc["summary"]
    if not s["fix_mrs"]:
        return "No fix MR yet."
    return (f"{s['fix_mrs']} fix MRs. {s['under_3_min']} came less than 3 min after the failed pipeline ended "
            f"(median {s['median_minutes']} min, slowest {s['max_minutes']} min). The judge passed in the gate of "
            f"{s['gate_judge_passed']}. Merged: {s['merged']}.")
