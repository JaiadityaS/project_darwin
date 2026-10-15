import copy
import subprocess

import pytest
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
