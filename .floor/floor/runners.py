"""H-1 on GitLab (F10.3): the build machine of each `main` pipeline and the CPU floor that the judge found.

The build job prints "build machine: <CPU model> (<x86-64 level>)" (`.gitlab/ci/facts.sh --cpu`), and the judge
job prints the CPU floor of the image in its table. Both come from the job logs, which a public project shows
without a token. A flip is two `main` pipelines next to each other with different floors. For each flip, the
compare API lists the changed files in the build inputs. A flip with no change there can come only from the
build machine.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import Callable

import requests

from .h1 import FLOOR_PATHS

# The build inputs on GitLab: upstream's floor paths and the CI file that runs `docker build`.
BUILD_PATHS = FLOOR_PATHS + (".gitlab-ci.yml",)
# Upstream's recipe. A change here (the canned config of a fix MR) ends the rows that test H-1.
RECIPE = ".devops/"
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_MACHINE = re.compile(r"build machine: (.+) \((x86-64-v[1-4])\)\s*$", re.M)
_FLOOR = re.compile(r"(?:^|\s)cpu\s+[a-z]+\s+(x86-64-v[1-4])\s", re.M)


def machine(log: str) -> tuple[str, str] | None:
    """The CPU model and the x86-64 level of the build machine, from a build job log."""
    match = _MACHINE.search(_ANSI.sub("", log))
    return (match.group(1).strip(), match.group(2)) if match else None


def floor(log: str) -> str | None:
    """The CPU floor of the image, from the table in a judge job log."""
    match = _FLOOR.search(_ANSI.sub("", log))
    return match.group(1) if match else None


def _latest(jobs: list[dict], name: str, statuses: tuple[str, ...]) -> dict | None:
    found = [j for j in jobs if j.get("name") == name and j.get("status") in statuses]
    return max(found, key=lambda j: j["id"]) if found else None


def build_changes(paths: list[str]) -> list[str]:
    """The paths that are build inputs (a folder in BUILD_PATHS ends with "/")."""
    return sorted(p for p in paths if any(p == b or (b.endswith("/") and p.startswith(b)) for b in BUILD_PATHS))


def rows(get: Callable[[str], list | dict], log: Callable[[int], str]) -> list[dict]:
    """One row for each `main` pipeline with a build, oldest first. `get(path)` gives the JSON of a GET on the
    project API, and `log(job_id)` gives the text of a job log."""
    found = []
    for pipeline in sorted(get("pipelines?ref=main&per_page=100"), key=lambda p: p["id"]):
        jobs = get(f"pipelines/{pipeline['id']}/jobs?per_page=100")
        build = _latest(jobs, "build", ("success",))
        if not build:
            continue
        judge = _latest(jobs, "judge", ("success", "failed"))
        cpu = machine(log(build["id"]))
        found.append({
            "pipeline": pipeline["id"], "url": pipeline.get("web_url"), "sha": pipeline["sha"],
            "created_at": pipeline.get("created_at"), "build_job": build["id"],
            "machine": cpu[0] if cpu else None, "machine_level": cpu[1] if cpu else None,
            "judge_job": judge["id"] if judge else None, "floor": floor(log(judge["id"])) if judge else None,
        })
    return found


def flips(found: list[dict], get: Callable[[str], list | dict]) -> list[dict]:
    """Pipelines next to each other with different floors, and the build inputs that changed between them."""
    known = [r for r in found if r["floor"]]
    out = []
    for a, b in zip(known, known[1:]):
        if a["floor"] == b["floor"]:
            continue
        if a["sha"] == b["sha"]:
            commits, paths = 0, []
        else:
            diff = get(f"repository/compare?from={a['sha']}&to={b['sha']}")
            commits = len(diff.get("commits") or [])
            paths = sorted({d[k] for d in diff.get("diffs") or [] for k in ("old_path", "new_path") if d.get(k)})
        out.append({"from": {k: a[k] for k in ("pipeline", "sha", "machine", "floor")},
                    "to": {k: b[k] for k in ("pipeline", "sha", "machine", "floor")},
                    "commits": commits, "changed_files": len(paths), "build_changes": build_changes(paths)})
    return out


def summary(found: list[dict], changes: list[dict]) -> dict:
    """The counts that the page and the CLI print. H-1 is a claim about upstream's recipe, so the counts stop at
    the first flip that changed a file in `.devops/` (a merged fix MR). The pipelines from there on are "repaired"
    and do not count."""
    known = [r for r in found if r["floor"] and r["machine"]]
    cut = next((f["to"]["pipeline"] for f in changes if any(p.startswith(RECIPE) for p in f["build_changes"])), None)
    recipe = [r for r in known if cut is None or r["pipeline"] < cut]
    repaired = [r for r in known if cut is not None and r["pipeline"] >= cut]
    changes = [f for f in changes if cut is None or f["to"]["pipeline"] < cut]
    machines: dict[str, dict] = {}
    for r in recipe:
        m = machines.setdefault(r["machine"], {"level": r["machine_level"], "pipelines": 0})
        m["pipelines"] += 1
    return {"pipelines": len(recipe), "machines": machines,
            "floor_is_machine_level": sum(r["floor"] == r["machine_level"] for r in recipe),
            "flips": len(changes), "flips_without_build_changes": sum(not f["build_changes"] for f in changes),
            "repaired": {"pipelines": len(repaired), "from": cut,
                         "floors": sorted({r["floor"] for r in repaired})}}


def verdict(s: dict) -> str:
    if not s["pipelines"]:
        return "not checked (no main pipeline with a build and a judge)"
    if len(s["machines"]) < 2:
        return "not shown: every main pipeline ran on the same CPU model"
    if s["floor_is_machine_level"] == s["pipelines"] and s["flips_without_build_changes"]:
        n = s["flips_without_build_changes"]
        return ("supported: in each main pipeline the CPU floor is the level of the build machine, and "
                f"{n} floor {'change' if n == 1 else 'changes'} came with no change to the build inputs")
    return "partly supported: see the rows"


def collect(api_url: str, project_id: str, web_url: str, session: requests.Session | None = None,
            timeout: float = 60) -> dict:
    """The rows, the flips and the counts, read from the API and the job logs now."""
    http = session or requests.Session()

    def get(path: str):
        response = http.get(f"{api_url}/projects/{project_id}/{path}", timeout=timeout)
        response.raise_for_status()
        return response.json()

    def log(job_id: int) -> str:
        for attempt in range(3):  # the raw log page sometimes gives a 5xx once
            response = http.get(f"{web_url}/-/jobs/{job_id}/raw", timeout=timeout)
            if response.status_code < 500:
                break
            time.sleep(2 * (attempt + 1))
        response.raise_for_status()
        return response.text

    found = rows(get, log)
    changes = flips(found, get)
    s = summary(found, changes)
    return {"project": str(project_id), "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "build_paths": list(BUILD_PATHS), "rows": found, "flips": changes, "summary": s, "verdict": verdict(s)}


def text(doc: dict) -> str:
    """The counts in words, for the CLI and the page."""
    s = doc["summary"]
    if not s["pipelines"]:
        return "No main pipeline with a build and a judge yet."
    parts = [f"{m['pipelines']} on {name} ({m['level']})"
             for name, m in sorted(s["machines"].items(), key=lambda kv: -kv[1]["pipelines"])]
    return (f"{s['pipelines']} main pipelines: " + ", ".join(parts) + ". "
            f"In {s['floor_is_machine_level']} of them the CPU floor is the level of the build machine. "
            f"{s['flips']} floor changes, {s['flips_without_build_changes']} with no change to the build inputs."
            + _repaired(s))


def _repaired(s: dict) -> str:
    r = s.get("repaired") or {}
    if not r.get("pipelines"):
        return ""
    n = r["pipelines"]
    return (f" From pipeline {r['from']}, a merged fix MR changed `.devops/`, so {n} later "
            f"{'pipeline does' if n == 1 else 'pipelines do'} not count (CPU floor {', '.join(r['floors'])}).")
