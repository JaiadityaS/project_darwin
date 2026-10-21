"""Tests for the repair loop rows (F4), with a fake GitLab API."""

from __future__ import annotations

from floor import repairs

BASE = "https://gitlab.example/p/-"
API = {
    "merge_requests?state=all&per_page=100": [
        {"iid": 10, "source_branch": "floor-fix/2969385744", "state": "opened", "created_at": "2026-10-20T21:07:53.437Z",
         "web_url": f"{BASE}/merge_requests/10"},
        {"iid": 3, "source_branch": "floor-fix/2961094614", "state": "merged", "created_at": "2026-10-19T00:06:26Z",
         "web_url": f"{BASE}/merge_requests/3"},
        {"iid": 11, "source_branch": "docs/readme", "state": "opened", "created_at": "2026-10-21T00:00:00Z",
         "web_url": f"{BASE}/merge_requests/11"},
    ],
    "pipelines/2969385744": {"id": 2969385744, "ref": "main", "finished_at": "2026-10-20T21:05:46.000Z",
                             "web_url": f"{BASE}/pipelines/2969385744"},
    "pipelines/2961094614": {"id": 2961094614, "ref": "main", "finished_at": "2026-10-19T00:04:15Z",
                             "web_url": f"{BASE}/pipelines/2961094614"},
    "merge_requests/10/pipelines": [{"id": 2969425658, "status": "success", "web_url": f"{BASE}/pipelines/2969425658"}],
    "merge_requests/3/pipelines": [{"id": 2961100000, "status": "failed", "web_url": f"{BASE}/pipelines/2961100000"},
                                   {"id": 2961110649, "status": "success", "web_url": f"{BASE}/pipelines/2961110649"}],
    "pipelines/2969385744/jobs?per_page=100": [{"id": 1, "name": "judge", "status": "failed"}],
    "pipelines/2961094614/jobs?per_page=100": [{"id": 2, "name": "judge", "status": "failed"}],
    "pipelines/2969425658/jobs?per_page=100": [{"id": 3, "name": "judge", "status": "success"},
                                               {"id": 4, "name": "check", "status": "success"}],
    "pipelines/2961110649/jobs?per_page=100": [{"id": 5, "name": "judge", "status": "failed"},
                                               {"id": 6, "name": "judge", "status": "success"}],
}


def test_rows():
    found = repairs.rows(API.__getitem__)
    assert [r["mr"] for r in found] == [3, 10]  # by MR number; a branch that is not a fix branch is not a row
    old, new = found
    assert new["failed_pipeline"] == 2969385744 and new["failed_judge"] == "failed"
    assert new["minutes"] == 2.1 and old["minutes"] == 2.2
    assert old["gate_pipeline"] == 2961110649  # the latest MR pipeline
    assert old["gate_judge"] == "success"  # the latest run of the judge job
    assert new["gate_url"] == f"{BASE}/pipelines/2969425658" and old["state"] == "merged"


def test_summary_and_text():
    doc = {"rows": repairs.rows(API.__getitem__)}
    doc["summary"] = repairs.summary(doc["rows"])
    assert doc["summary"] == {"fix_mrs": 2, "under_3_min": 2, "median_minutes": 2.2, "max_minutes": 2.2,
                              "gate_judge_passed": 2, "merged": 1}
    assert repairs.text(doc).startswith("2 fix MRs. 2 came less than 3 min after the failed pipeline ended")
    assert repairs.text({"rows": [], "summary": repairs.summary([])}) == "No fix MR yet."


def test_helpers():
    assert repairs.minutes(None, "2026-10-20T21:07:53Z") is None
    assert repairs.judge_status([{"id": 1, "name": "build", "status": "success"}]) is None
