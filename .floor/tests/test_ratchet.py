import copy
import subprocess

import pytest
import requests
import yaml

from floor import policy, ratchet
from floor.cli import main

NOTICE = """## Leave-Behind Notice
Floor change:     cpu: x86-64-v1 → x86-64-v3
Reason:           test
Approved by:      @owner
"""


@pytest.fixture
def old():
    return policy.load()


def test_no_change(old):
    assert ratchet.check(old, copy.deepcopy(old), {}) == {"ok": True, "changes": [], "blocked": []}


def test_stricter_needs_no_notice(old):
    new = copy.deepcopy(old)
    new["memory_mb"]["tiny"] = 256
    result = ratchet.check(old, new, {})
    assert result["ok"]
    assert {r["direction"] for r in result["changes"]} == {"stricter"}


def test_looser_cpu_is_blocked_without_notice(old):
    new = copy.deepcopy(old)
    new["cpu"]["x86_64_min_level"] = "x86-64-v3"
    result = ratchet.check(old, new, {})
    assert not result["ok"]
    assert {r["artifact"] for r in result["blocked"]} == {None}  # the server entry keeps v1
    assert ratchet.check(old, new, {"0001.md": NOTICE})["ok"]


def test_looser_artifact_and_other_dimensions(old):
    new = copy.deepcopy(old)
    new["artifacts"]["server"]["cpu"]["x86_64_min_level"] = "x86-64-v2"
    new["connectivity"]["offline_required"] = False
    new["cpu"]["emulate"] = ["qemu64"]
    new["memory_mb"]["base"] = 2048
    result = ratchet.check(old, new, {"0001.md": NOTICE})
    blocked = {(r["artifact"], r["field"]) for r in result["blocked"]}
    assert ("server", "offline_required") in blocked and (None, "memory_mb.base") in blocked
    assert not any(r["dimension"] == "cpu" for r in result["blocked"])


def test_incomplete_notice_does_not_count(old):
    new = copy.deepcopy(old)
    new["cpu"]["x86_64_min_level"] = "x86-64-v2"
    template = NOTICE.replace("@owner", "<code owner>")
    assert ratchet.notice_dimensions(template) is None
    assert not ratchet.check(old, new, {"t.md": template})["ok"]
    assert ratchet.notice_dimensions("Floor change: trade-off between cpu and memory_mb\nApproved by: @a\n") == {"cpu", "memory"}


def test_cli_with_git(tmp_path, monkeypatch, capsys):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    pol = tmp_path / ".floor" / "policy.yml"
    pol.parent.mkdir()
    pol.write_text(policy.DEFAULT_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    doc = yaml.safe_load(pol.read_text(encoding="utf-8"))
    doc["cpu"]["x86_64_min_level"] = "x86-64-v3"
    pol.write_text(yaml.safe_dump(doc), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["ratchet", str(pol), "--base", "main"]) == 1
    assert "NEEDS A MERGED NOTICE" in capsys.readouterr().out
    notices = tmp_path / ".floor" / "notices"
    notices.mkdir()
    (notices / "0001-cpu.md").write_text(NOTICE, encoding="utf-8")
    git("add", ".floor/notices")
    git("commit", "-q", "-m", "notice")
    assert main(["ratchet", str(pol), "--base", "main"]) == 0
    assert "notice: 0001-cpu.md" in capsys.readouterr().out


def test_code_owners():
    text = "# x\n[Floor gate]\n/.floor/notices/ @old\n/.floor/ @all\n/.floor/notices/ @owner @second  # note\n"
    assert ratchet.code_owners(text) == ["owner", "second"]
    assert ratchet.code_owners("/.floor/ @all\n") == []


def test_approvers():
    mr = {"iid": 4, "state": "merged", "target_branch": "main", "web_url": "https://gitlab.example/mr/4"}
    docs = {"/repository/commits/abc/merge_requests": [{**mr, "iid": 3, "state": "closed"}, mr],
            "/merge_requests/4/approvals": {"approved_by": [{"user": {"username": "owner"}}]}}
    assert ratchet.approvers("abc", "main", docs.__getitem__) == ("https://gitlab.example/mr/4", ["owner"])
    with pytest.raises(LookupError):
        ratchet.approvers("abc", "dev", docs.__getitem__)


def test_cli_with_approvals(tmp_path, monkeypatch, capsys):
    """F6.1: in CI the "Approved by" text is not enough; the GitLab approvals of the notice MR decide."""
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    pol = tmp_path / ".floor" / "policy.yml"
    (tmp_path / ".floor" / "notices").mkdir(parents=True)
    (tmp_path / ".gitlab").mkdir()
    (tmp_path / ".gitlab" / "CODEOWNERS").write_text("/.floor/notices/ @owner\n", encoding="utf-8")
    pol.write_text(policy.DEFAULT_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / ".floor" / "notices" / "0001-cpu.md").write_text(NOTICE, encoding="utf-8")
    git("add", ".")
    git("commit", "-q", "-m", "base and notice")
    doc = yaml.safe_load(pol.read_text(encoding="utf-8"))
    doc["cpu"]["x86_64_min_level"] = "x86-64-v3"
    pol.write_text(yaml.safe_dump(doc), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    approved = []

    class Resp:
        def __init__(self, doc):
            self.doc = doc

        def raise_for_status(self):
            if self.doc is None:
                raise requests.HTTPError("404")

        def json(self):
            return self.doc

    class Session:
        def get(self, url, timeout):
            path = url.removeprefix("https://gitlab.example/api/v4/projects/5")
            if path.startswith("/repository/commits/") and path.endswith("/merge_requests"):
                return Resp([{"iid": 9, "state": "merged", "target_branch": "main", "web_url": "https://mr/9"}])
            if path == "/merge_requests/9/approvals":
                return Resp({"approved_by": [{"user": {"username": u}} for u in approved]} if approved != ["404"] else None)
            raise AssertionError(path)

    monkeypatch.setattr("floor.cli.requests.Session", Session)
    args = ["ratchet", str(pol), "--base", "main", "--approvals", "https://gitlab.example/api/v4/projects/5",
            "--default-branch", "main", "--humans", "owner"]
    for who, rc, text in ((["owner"], 0, "notice: 0001-cpu.md"),
                          ([], 1, "https://mr/9: no code-owner approval"),
                          (["owner", "floor-agent"], 1, "approved by an agent or bot account: floor-agent"),
                          (["404"], 1, "does not count: no approvals from the GitLab API")):
        approved[:] = who
        assert main(args) == rc
        assert text in capsys.readouterr().out
    approved[:] = ["second"]  # a human, but not the code owner, and not the name on the "Approved by" line
    assert main(args[:-1] + ["owner second"]) == 1
    out = capsys.readouterr().out
    assert "no code-owner approval" in out and "names none of the approvers (second)" in out
    assert main(args[:4] + ["--approvals", "https://gitlab.example/api/v4/projects/5"]) == 2


def test_check_job_verifies_approvals():
    from pathlib import Path
    script = (Path(__file__).resolve().parents[2] / ".gitlab" / "ci" / "check.sh").read_text(encoding="utf-8")
    assert ('floor ratchet --base "$base" --approvals "$CI_API_V4_URL/projects/$CI_PROJECT_ID" '
            '--default-branch "$CI_DEFAULT_BRANCH"') in script
