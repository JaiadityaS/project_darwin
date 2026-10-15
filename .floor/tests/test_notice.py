from pathlib import Path

from floor import notice, ratchet
from floor.cli import main

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (ROOT / ".gitlab" / "merge_request_templates" / "Leave-Behind-Notice.md").read_text(encoding="utf-8")

FILLED = """## Leave-Behind Notice
Floor change:     cpu: x86-64-v1 → x86-64-v3
Reason:           the v1 build is 4x slower on the service hardware
Tried first:      GGML_CPU_ALL_VARIANTS (job 12), canned config (job 13)
Who is affected:  pre-2013 x86 CPUs; proxy: Steam survey AVX2 share, 2-5%
ΔM (scenario):    0.4–2.1 kgCO₂e (inputs in the job)
Guidance:         use the -floor.3 release or the all-variants artifact
Approved by:      @owner
"""


def test_template_has_every_field():
    assert set(notice.parse(TEMPLATE)) == set(notice.FIELDS)
    assert len(notice.problems(TEMPLATE)) == len(notice.FIELDS)


def test_filled_notice():
    assert notice.problems(FILLED) == []
    assert ratchet.notice_dimensions(FILLED) == {"cpu"}


def test_draft_allows_no_approver():
    draft = FILLED.replace("@owner", "")
    assert notice.problems(draft) == ["Approved by: missing"]
    assert notice.problems(draft, draft=True) == []
    assert ratchet.notice_dimensions(draft) is None


def test_missing_heading_and_field():
    text = FILLED.replace("## Leave-Behind Notice\n", "").replace("Guidance:", "Advice:")
    assert notice.problems(text) == ["no '## Leave-Behind Notice' heading", "Guidance: missing"]


def test_approvals():
    owners, bots = ["alice", "bob"], ["floor-agent", "merge-bot"]
    assert notice.approval_problems(["alice"], owners, bots) == []
    assert notice.approval_problems(["carol"], owners, bots) == ["no code-owner approval"]
    assert notice.approval_problems(["alice", "merge-bot"], owners, bots) == [
        "approved by an agent or bot account: merge-bot"]
    assert notice.approval_problems(["merge-bot"], owners + ["merge-bot"], bots)[-1] == "no code-owner approval"


def test_cli(tmp_path, capsys):
    good, bad = tmp_path / "0001-cpu.md", tmp_path / "0002-memory.md"
    good.write_text(FILLED, encoding="utf-8")
    bad.write_text(TEMPLATE, encoding="utf-8")
    assert main(["notice", str(good)]) == 0
    assert main(["notice", str(good), str(bad)]) == 1
    assert "placeholder" in capsys.readouterr().out
