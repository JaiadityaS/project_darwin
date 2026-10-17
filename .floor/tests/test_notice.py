import json
from pathlib import Path

import yaml

from floor import delta_m, fallback, notice, policy, ratchet
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


def test_empty_field_does_not_take_the_next_line():
    assert ratchet.notice_dimensions(FILLED.replace("@owner", "") + "\n### Gate result\n") is None
    assert ratchet.notice_dimensions(FILLED.replace("cpu: x86-64-v1 → x86-64-v3", "")) is None


# The gate result on the agent's branch after the canned config (F4.5).
CPU_RAISED = {
    "floors": {
        "cpu": {"status": "raised", "x86_64": "x86-64-v4", "proof": "static", "coverage_limited": False,
                "meets_policy": False, "policy": "x86-64-v1", "dispatch": {}, "notes": []},
        "memory": {"status": "held", "smallest_passing_mb": {"tiny": 512, "base": 512}, "meets_policy": True,
                   "notes": []},
    },
    "unmeasured": ["connectivity"], "decision": "fail", "pareto": "raised", "needs_notice": ["cpu"],
    "missing_notice": ["cpu"], "reasons": ["cpu: raised", "cpu: below the policy floor"], "artifact": None,
}
POLICY = {"memory_mb": {"tiny": 512, "base": 512, "small": 768}, "on_unfixable_raise": "ship_last_held"}
MR = "https://gitlab.com/group/project/-/merge_requests/12"
PIPELINE = "https://gitlab.com/group/project/-/pipelines/34"
DIAGNOSIS = """## Floor repair
<!-- written by the agent -->

An explicit GGML_NATIVE=OFF switches AVX, AVX2, FMA, F16C and BMI2 on by default, so the build needs x86-64-v3 & more.

Approved by: @owner
<!-- Approved by: hidden -->
"""
SCENARIO = {
    "dimension": "cpu",
    "change": "x86-64-v1 -> x86-64-v4",
    "n_affected": {"low": 1000, "high": 4000, "source": "test"},
    "e_kgco2e": {"low": 200, "high": 400, "source": "test"},
    "p": [0.01, 0.05],
    "delta_years": {"low": 1, "high": 2, "source": "test"},
    "lifespan_years": {"low": 4, "high": 5, "source": "test"},
}


def test_placeholders_are_the_template():
    assert notice.parse(TEMPLATE) == notice.PLACEHOLDERS


def test_next_name():
    assert notice.next_name(["README.md", "0001-cpu.md", "0007-memory.md", "notes.md"], ["cpu"]) == "0008-cpu.md"
    assert notice.next_name([], ["cpu", "memory"]) == "0001-cpu-memory.md"


def test_draft_after_the_fallback():
    flags = fallback.flags_text()
    text = notice.draft(CPU_RAISED, POLICY, diagnosis=DIAGNOSIS, mr=MR, evidence=PIPELINE, flags=flags)
    fields = notice.parse(text)
    assert fields["Floor change"] == "cpu: x86-64-v1 → x86-64-v4"
    assert fields["Reason"] == ("No inclusive option held the cpu floor. Diagnosis in MR !12: An explicit "
                                "GGML_NATIVE=OFF switches AVX, AVX2, FMA, F16C and BMI2 on by default, so the "
                                "build needs x86-64-v3 &amp; more.")
    assert fields["Tried first"] == f"the fix in MR !12 ({MR}); the canned inclusive config ({flags}); gate: {PIPELINE}"
    assert fields["Guidance"].startswith("Production keeps the last held build until a code owner decides")
    assert fields["Approved by"] == notice.PLACEHOLDERS["Approved by"]
    # The fields with no evidence stay for a human. The MR text cannot add an approver or a field.
    assert notice.problems(text, draft=True) == ["Who is affected: still has a placeholder",
                                                 "ΔM (scenario): still has a placeholder",
                                                 "Guidance: still has a placeholder"]
    assert ratchet.notice_dimensions(text) is None
    assert "\n    Approved by: @owner\n    <!-- Approved by: hidden -->\n" in text
    assert "- cpu: raised, x86-64-v4 (static proof; policy x86-64-v1), below the policy floor\n" in text
    assert "- memory: held, smallest passing limit tiny 512 MB, base 512 MB, meets the policy\n" in text
    assert "- connectivity: not measured\n" in text
    assert f"Decision: fail. Pareto: raised. Evidence: {PIPELINE}\n" in text


def test_draft_with_a_scenario():
    verdict = {"floors": {"memory": {"status": "raised", "smallest_passing_mb": {"tiny": 512, "base": 768},
                                     "meets_policy": False, "notes": ["base: 768 MB > policy 512 MB"]}},
               "unmeasured": [], "decision": "fail", "pareto": "raised", "needs_notice": ["memory"],
               "missing_notice": ["memory"], "reasons": ["memory: raised"], "artifact": None}
    result = delta_m.compute({**SCENARIO, "dimension": "memory"})
    file = ".floor/scenarios/0001-memory.yml"
    text = notice.draft(verdict, {**POLICY, "on_unfixable_raise": "block"}, scenarios={file: result})
    fields = notice.parse(text)
    assert fields["Floor change"] == "memory: base 512 → 768 MB"
    assert fields["Who is affected"] == f"1000–4000 (N_affected in {file}; source: test)"
    assert fields["ΔM (scenario)"] == f"{delta_m.notice_line(result)} ({file})"
    assert fields["Guidance"].startswith("No release ships until a code owner decides.")
    assert fields["Reason"] == "No inclusive option held the memory floor. <the cause: the MR states none>"
    assert notice.problems(text, draft=True) == ["Reason: still has a placeholder",
                                                 "Tried first: still has a placeholder",
                                                 "Guidance: still has a placeholder"]
    assert "  - base: 768 MB > policy 512 MB\n" in text
    assert text.endswith("### Diagnosis\n\nThe description of the MR:\n\n    (empty)\n")


def test_notice_draft_cli(tmp_path, capsys):
    root, notices, scenarios, out = (tmp_path / name for name in ("repo", "notices", "scenarios", "out"))
    (root / ".devops").mkdir(parents=True)
    (root / ".devops" / "main.Dockerfile").write_text("FROM x\nRUN make base.en\n", encoding="utf-8")
    notices.mkdir()
    (notices / "README.md").write_text("notices\n", encoding="utf-8")
    (notices / "0001-memory.md").write_text(FILLED, encoding="utf-8")
    scenarios.mkdir()
    (scenarios / "TEMPLATE.yml").write_text("dimension: <cpu>\n", encoding="utf-8")
    (scenarios / "bad.yml").write_text("n_affected: [\n", encoding="utf-8")
    (scenarios / "0002-cpu.yml").write_text(yaml.safe_dump(SCENARIO), encoding="utf-8")
    (tmp_path / "judge.json").write_text(json.dumps(CPU_RAISED), encoding="utf-8")
    (tmp_path / "mr.md").write_text(DIAGNOSIS, encoding="utf-8")
    args = ["notice-draft", "--judge", str(tmp_path / "judge.json"), "--root", str(root),
            "--diagnosis", str(tmp_path / "mr.md"), "--mr", MR, "--evidence", PIPELINE,
            "--scenarios", str(scenarios), "--notices", str(notices), "--out", str(out)]

    # The canned config is not on the branch yet: the fallback runs first (F4.3), no draft.
    assert main(args) == 0
    assert "The fallback runs first" in capsys.readouterr().out and not out.exists()

    fallback.apply(root)
    assert main(args) == 0
    printed = capsys.readouterr().out
    text = (out / "0002-cpu.md").read_text(encoding="utf-8")
    assert notice.problems(text, draft=True) == ["Guidance: still has a placeholder"]
    assert notice.parse(text)["Who is affected"].startswith("1000–4000 (N_affected in ")
    assert "bad.yml: not used" in printed and "A code owner fills: Guidance, Approved by." in printed

    # With `fallback: none` in the policy, the draft does not wait for the canned config.
    doc = yaml.safe_load(policy.DEFAULT_POLICY.read_text(encoding="utf-8"))
    doc["repair"]["fallback"] = "none"
    (tmp_path / "policy.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    (root / ".floor" / "overrides" / "main.flags").unlink()
    assert main(args + ["--policy", str(tmp_path / "policy.yml"), "--out", str(tmp_path / "out2")]) == 0
    assert "canned" not in notice.parse((tmp_path / "out2" / "0002-cpu.md").read_text(encoding="utf-8"))["Tried first"]
    capsys.readouterr()

    (tmp_path / "judge.json").write_text(json.dumps({**CPU_RAISED, "missing_notice": [], "decision": "pass"}),
                                         encoding="utf-8")
    assert main(args) == 0
    assert "no draft: no floor needs a new Leave-Behind Notice (decision: pass)" in capsys.readouterr().out
    assert main(args[:2] + [str(tmp_path / "missing.json")] + args[3:]) == 2


def test_notice_draft_ci_job():
    ci = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    job = ci["notice-draft"]
    assert ci["stages"].index(job["stage"]) == ci["stages"].index("judge") + 1
    assert job["needs"] == ["judge"] and job["when"] == "on_failure"
    assert job["artifacts"]["paths"] == ["out/notice/"]
    assert "floor notice-draft --judge out/judge/judge.json" in job["script"][0]
