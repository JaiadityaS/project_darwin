import json
from pathlib import Path

from floor import release
from floor.cli import main

ROOT = Path(__file__).resolve().parents[2]
SHA = "9" * 40
MR = {"iid": 7, "state": "merged", "source_branch": "floor-fix/111", "target_branch": "main",
      "web_url": "https://gitlab.example/g/p/-/merge_requests/7"}


def api(merge_requests, pipeline, tags=()):
    calls = []

    def get(path):
        calls.append(path)
        if path == f"/repository/commits/{SHA}/merge_requests":
            return merge_requests
        if path == "/pipelines/111":
            return pipeline
        if path.startswith("/repository/tags?search=^"):
            return [{"name": t} for t in tags]
        raise AssertionError(path)
    get.calls = calls
    return get


def test_next_tag():
    assert release.next_tag("v1.8.2", []) == "v1.8.2-floor.1"
    assert release.next_tag("v1.8.2", ["v1.8.2-floor.1", "v1.8.2-floor.3", "v1.8.20-floor.9"]) == "v1.8.2-floor.4"


def test_plan_after_a_fix_of_a_tag():
    get = api([MR], {"id": 111, "ref": "v1.8.2", "tag": True}, ["v1.8.2-floor.1"])
    assert release.plan(SHA, "main", get) == {"tag": "v1.8.2-floor.2", "base": "v1.8.2", "pipeline": 111,
                                              "mr": MR["web_url"]}


def test_plan_skips():
    # A commit with no merged fix MR (for example a sync push) gets no release.
    assert "not the merge of a floor-fix/ MR" in release.plan(SHA, "main", api([], {}))["skip"]
    assert "skip" in release.plan(SHA, "main", api([{**MR, "state": "opened"}], {}))
    assert "skip" in release.plan(SHA, "main", api([{**MR, "source_branch": "feature/x"}], {}))
    assert "skip" in release.plan(SHA, "main", api([{**MR, "target_branch": "dev"}], {}))
    # A fix of a branch pipeline (not a tag) holds the branch; the next tag releases.
    assert "not a tag pipeline" in release.plan(SHA, "main", api([MR], {"ref": "main", "tag": False}))["skip"]
    assert "-floor tag" in release.plan(SHA, "main", api([MR], {"ref": "v1.8.2-floor.1", "tag": True}))["skip"]


def test_notes():
    plan = {"tag": "v1.8.2-floor.1", "base": "v1.8.2", "pipeline": 111, "mr": MR["web_url"]}
    text = release.notes(plan, "## Floor diff\n| cpu | x86-64-v4 | x86-64-v1 | lowered |\n", "cosign verify-attestation x\n")
    assert "pipeline 111" in text and MR["web_url"] in text and "| cpu |" in text
    assert "```\ncosign verify-attestation x\n```" in text
    assert "cosign" not in release.notes(plan, "diff", None)
    with_herald = release.notes(plan, "diff", None, "## Who this release serves\n\n- **CPU:** any\n")
    assert with_herald.index("## Who this release serves") < with_herald.index("pipeline 111")


def test_cli_dry_run(tmp_path, monkeypatch, capsys):
    get = api([MR], {"id": 111, "ref": "v1.8.2", "tag": True})

    class Resp:
        def __init__(self, doc):
            self.doc = doc

        def raise_for_status(self):
            pass

        def json(self):
            return self.doc

    class Session:
        def get(self, url, timeout):
            return Resp(get(url.removeprefix("https://gitlab.example/api/v4/projects/5")))

        def post(self, *a, **k):
            raise AssertionError("a dry run posts nothing")

    monkeypatch.setattr("floor.cli.requests.Session", Session)
    diff = tmp_path / "diff.md"
    diff.write_text("## Floor diff\n", encoding="utf-8")
    out = tmp_path / "release.json"
    args = ["release", "--sha", SHA, "--default-branch", "main", "--api", "https://gitlab.example/api/v4",
            "--project", "5", "--diff", str(diff), "--verify", str(tmp_path / "missing.txt"),
            "--link", "Floor Manifest=https://gitlab.example/j/1/artifacts/file/m.json", "--out", str(out), "--dry-run"]
    assert main(args) == 0
    assert "release v1.8.2-floor.1 from 99999999" in capsys.readouterr().out
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["tag_name"] == body["name"] == "v1.8.2-floor.1" and body["ref"] == SHA
    assert body["assets"]["links"] == [{"name": "Floor Manifest", "url": "https://gitlab.example/j/1/artifacts/file/m.json"}]
    monkeypatch.delenv("CI_JOB_TOKEN", raising=False)
    assert main(args[:-1]) == 2  # no job token: no release outside CI
    assert main(args[:-3] + ["--link", "bad", "--dry-run"]) == 2


def test_release_ci_job():
    """F4.4, D-024: on the default branch after attest; the job token only; no pipeline for a -floor tag."""
    import yaml
    ci = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    job = ci["release"]
    assert job["needs"] == ["judge", "attest", "herald"] and job["rules"] == [{"if": "$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH"}]
    script = "\n".join(job["script"])
    assert 'floor release --sha "$CI_COMMIT_SHA"' in script and "--dry-run" not in script
    assert "TOKEN" not in script  # floor release reads CI_JOB_TOKEN itself; no other token
    rules = ci["workflow"]["rules"]
    skip = {"if": r"$CI_COMMIT_TAG =~ /-floor\.[0-9]+$/", "when": "never"}
    assert rules.index(skip) < rules.index({"if": "$CI_COMMIT_TAG"})
    for name in ("judge", "attest"):
        assert f'echo "$CI_JOB_URL" > out/{name}/job-url.txt' in "\n".join(ci[name]["script"])
