"""Tests for H-1 on GitLab (F10.3), with a fake GitLab API and fake job logs."""

from __future__ import annotations

from floor import runners

BASE = "https://gitlab.example/p/-"
INTEL = "INTEL(R) XEON(R) PLATINUM 8581C CPU @ 2.10GHz"
AMD = "AMD EPYC 7B13"
API = {
    "pipelines?ref=main&per_page=100": [
        {"id": 30, "sha": "c" * 40, "web_url": f"{BASE}/pipelines/30", "created_at": "2026-10-21T07:55:00Z"},
        {"id": 10, "sha": "a" * 40, "web_url": f"{BASE}/pipelines/10", "created_at": "2026-10-20T19:46:00Z"},
        {"id": 20, "sha": "b" * 40, "web_url": f"{BASE}/pipelines/20", "created_at": "2026-10-21T05:21:00Z"},
        {"id": 40, "sha": "d" * 40, "web_url": f"{BASE}/pipelines/40", "created_at": "2026-10-21T09:00:00Z"},
    ],
    "pipelines/10/jobs?per_page=100": [{"id": 101, "name": "build", "status": "success"},
                                       {"id": 102, "name": "judge", "status": "failed"}],
    "pipelines/20/jobs?per_page=100": [{"id": 201, "name": "build", "status": "failed"},
                                       {"id": 203, "name": "build", "status": "success"},
                                       {"id": 202, "name": "judge", "status": "failed"}],
    "pipelines/30/jobs?per_page=100": [{"id": 301, "name": "build", "status": "success"},
                                       {"id": 302, "name": "judge", "status": "failed"}],
    "pipelines/40/jobs?per_page=100": [{"id": 401, "name": "build", "status": "failed"}],
    f"repository/compare?from={'a' * 40}&to={'b' * 40}": {
        "commits": [{}], "diffs": [{"old_path": ".gitlab-ci.yml", "new_path": ".gitlab-ci.yml"},
                                   {"old_path": "README.md", "new_path": "README.md"}]},
    f"repository/compare?from={'b' * 40}&to={'c' * 40}": {
        "commits": [{}], "diffs": [{"old_path": ".floor/floor/page.py", "new_path": ".floor/floor/page.py"},
                                   {"old_path": "README.md", "new_path": "README.md"}]},
}


def _judge(level: str) -> str:
    return (f"2026-10-21T05:29:14.189240Z 01O FLOOR         STATUS  VALUE      PROOF   POLICY\n"
            f"2026-10-21T05:29:14.189244Z 01O \x1b[0;31mcpu           raised  {level}  static  NOT met\x1b[0m\n"
            f"2026-10-21T05:29:14.402458Z 01O | cpu | - | {level} | raised |\n")


LOGS = {
    101: f"Running on CPU: {AMD} (avx, avx2)\nbuild machine: {AMD} (x86-64-v3)\n",
    102: _judge("x86-64-v3"),
    203: f"build machine: {INTEL} (x86-64-v4)\r\n",
    202: _judge("x86-64-v4"),
    301: f"2026-10-21T07:58:51.000290Z 01O build machine: {AMD} (x86-64-v3)\n",
    302: _judge("x86-64-v3"),
}


def _doc() -> dict:
    found = runners.rows(API.__getitem__, LOGS.__getitem__)
    changes = runners.flips(found, API.__getitem__)
    s = runners.summary(found, changes)
    return {"rows": found, "flips": changes, "summary": s, "verdict": runners.verdict(s)}


def test_parsers():
    assert runners.machine(LOGS[301]) == (AMD, "x86-64-v3")
    assert runners.machine(LOGS[203]) == (INTEL, "x86-64-v4")
    assert runners.machine("no machine here") is None
    assert runners.floor(LOGS[102]) == "x86-64-v3"  # the colour codes go; the Markdown table is not the match
    assert runners.floor("cpu: raised\n| cpu | - | x86-64-v2 | raised |\n") is None


def test_rows_and_flips():
    doc = _doc()
    assert [r["pipeline"] for r in doc["rows"]] == [10, 20, 30]  # oldest first; no successful build, no row
    assert doc["rows"][1]["build_job"] == 203 and doc["rows"][1]["machine"] == INTEL
    assert [(f["from"]["pipeline"], f["to"]["pipeline"]) for f in doc["flips"]] == [(10, 20), (20, 30)]
    first, second = doc["flips"]
    assert first["build_changes"] == [".gitlab-ci.yml"] and first["changed_files"] == 2
    assert second["build_changes"] == [] and second["commits"] == 1
    assert second["to"] == {"pipeline": 30, "sha": "c" * 40, "machine": AMD, "floor": "x86-64-v3"}


def test_summary_text_and_verdict():
    doc = _doc()
    assert doc["summary"] == {"pipelines": 3, "machines": {AMD: {"level": "x86-64-v3", "pipelines": 2},
                                                           INTEL: {"level": "x86-64-v4", "pipelines": 1}},
                              "floor_is_machine_level": 3, "flips": 2, "flips_without_build_changes": 1,
                              "repaired": {"pipelines": 0, "from": None, "floors": []}}
    assert doc["verdict"].startswith("supported: in each main pipeline the CPU floor is the level of the build "
                                     "machine, and 1 floor change came")
    assert runners.text(doc) == (f"3 main pipelines: 2 on {AMD} (x86-64-v3), 1 on {INTEL} (x86-64-v4). In 3 of them "
                                 "the CPU floor is the level of the build machine. 2 floor changes, 1 with no change "
                                 "to the build inputs.")
    one = runners.summary(doc["rows"][1:2], [])
    assert runners.verdict(one).startswith("not shown")
    assert runners.text({"summary": runners.summary([], [])}) == "No main pipeline with a build and a judge yet."


def test_repaired_pipelines_do_not_count():
    """A merged fix MR changes `.devops/`. From then on the floor is no longer the level of the build machine, and
    H-1 (a claim about upstream's recipe) must not count those pipelines."""
    doc = _doc()
    fixed = {"pipeline": 50, "url": f"{BASE}/pipelines/50", "sha": "e" * 40, "created_at": "2026-10-25T21:18:00Z",
             "build_job": 501, "machine": INTEL, "machine_level": "x86-64-v4", "judge_job": 502, "floor": "x86-64-v1"}
    later = dict(fixed, pipeline=60, sha="f" * 40)
    found = doc["rows"] + [fixed, later]
    fix = {"from": {"pipeline": 30, "sha": "c" * 40, "machine": AMD, "floor": "x86-64-v3"},
           "to": {"pipeline": 50, "sha": "e" * 40, "machine": INTEL, "floor": "x86-64-v1"},
           "commits": 2, "changed_files": 8, "build_changes": [".devops/main.Dockerfile"]}
    s = runners.summary(found, doc["flips"] + [fix])
    assert s["pipelines"] == 3 and s["floor_is_machine_level"] == 3 and s["flips"] == 2
    assert s["repaired"] == {"pipelines": 2, "from": 50, "floors": ["x86-64-v1"]}
    assert runners.verdict(s).startswith("supported:")
    assert runners.text({"summary": s}).endswith(
        "From pipeline 50, a merged fix MR changed `.devops/`, so 2 later pipelines do not count (CPU floor x86-64-v1).")
    # A flip that changed only .gitlab-ci.yml is not a recipe change: every row still counts.
    ci = dict(fix, build_changes=[".gitlab-ci.yml"])
    s = runners.summary(found, doc["flips"] + [ci])
    assert s["pipelines"] == 5 and s["repaired"]["pipelines"] == 0
    assert runners.verdict(s) == "partly supported: see the rows"


def test_build_changes():
    assert runners.build_changes([".devops/main.Dockerfile", "ggml/src/ggml-cpu/x.c", "ggml/include/ggml.h",
                                  ".gitlab-ci.yml", ".gitlab/ci/check.sh", "CMakeLists.txt", "examples/CMakeLists.txt"]) == [
        ".devops/main.Dockerfile", ".gitlab-ci.yml", "CMakeLists.txt", "ggml/src/ggml-cpu/x.c"]
