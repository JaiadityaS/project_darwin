import copy

import pytest

from floor import judge, policy
from floor.cli import main


@pytest.fixture
def doc():
    return policy.load()


def scan(level, errors=()):
    return {"floor": {"level": level, "extras": [], "sources": []}, "files": {"errors": list(errors)}}


def run(cpu, level, result, variant=None):
    return {"cpu": cpu, "cpu_level": f"x86-64-v{level}", "result": result, "loaded_variant": variant}


def probe(*runs):
    return {"runs": list(runs)}


def test_repo_policy_is_valid(doc):
    assert doc["cpu"]["x86_64_min_level"] == "x86-64-v1"
    assert doc["connectivity"]["offline_required"] is True


@pytest.mark.parametrize("change", [
    lambda d: d["cpu"].update(x86_64_min_level="x86-64-v5"),
    lambda d: d.update(colour="red"),
    lambda d: d["memory_mb"].update(tiny=10),
    lambda d: d.pop("connectivity"),
    lambda d: d["artifacts"]["server"].update(language={}),
])
def test_bad_policy_is_refused(doc, change):
    bad = copy.deepcopy(doc)
    change(bad)
    with pytest.raises(policy.PolicyError):
        policy.validate(bad)


def test_artifact_override(doc):
    doc = copy.deepcopy(doc)
    doc["artifacts"]["server"]["cpu"]["x86_64_min_level"] = "x86-64-v2"
    resolved = policy.for_artifact(doc, "server")
    assert resolved["cpu"]["x86_64_min_level"] == "x86-64-v2"
    assert resolved["cpu"]["emulate"] == doc["cpu"]["emulate"]
    assert "artifacts" not in resolved
    assert policy.for_artifact(doc, "other")["cpu"]["x86_64_min_level"] == "x86-64-v1"
    assert doc["cpu"]["x86_64_min_level"] == "x86-64-v1"


def test_cpu_static_held_and_raised(doc):
    assert judge.judge_cpu(doc["cpu"], scan("x86-64-v1"))["status"] == "held"
    raised = judge.judge_cpu(doc["cpu"], scan("x86-64-v3"))
    assert raised["status"] == "raised" and raised["meets_policy"] is False
    assert judge.judge_cpu(doc["cpu"], scan("x86-64-v3"), previous="x86-64-v4")["status"] == "lowered"
    assert judge.judge_cpu(doc["cpu"], scan("none"))["x86_64"] == "x86-64-v1"


def test_cpu_dynamic_only_is_coverage_limited(doc):
    result = judge.judge_cpu(doc["cpu"], None, probe(run("qemu64", 1, "pass", "x64"), run("Nehalem", 2, "pass", "sse42")))
    assert result["status"] == "held" and result["coverage_limited"] and result["proof"] == "dynamic"
    assert result["dispatch"] == {"qemu64": "x64", "Nehalem": "sse42"}
    lowered = judge.judge_cpu(doc["cpu"], None, probe(run("qemu64", 1, "pass")), previous="x86-64-v3")
    assert lowered["status"] == "held"


def test_cpu_contradiction_is_inconclusive(doc):
    result = judge.judge_cpu(doc["cpu"], scan("x86-64-v1"), probe(run("qemu64", 1, "fail")))
    assert result["status"] == "inconclusive"
    ok = judge.judge_cpu(doc["cpu"], scan("x86-64-v3"), probe(run("Nehalem", 2, "fail"), run("EPYC-Milan", 3, "pass")),
                         previous="x86-64-v3")
    assert ok["status"] == "held"


def test_cpu_scan_errors_and_bad_controls(doc):
    assert judge.judge_cpu(doc["cpu"], scan("x86-64-v1", ["a.so"]))["status"] == "inconclusive"
    result = judge.judge_cpu(doc["cpu"], scan("x86-64-v1"), probe(run("qemu64", 1, "inconclusive")))
    assert result["status"] == "held" and result["dispatch"] == {}
    assert any("controls failed" in note for note in result["notes"])


def test_memory_and_connectivity(doc):
    assert judge.judge_memory({}, None) is None
    mem = judge.judge_memory({"tiny": 300}, {"tiny": 350}, {"tiny": 300})
    assert mem["status"] == "raised" and mem["meets_policy"] is False
    assert judge.judge_memory({"tiny": None}, {"tiny": 250})["status"] == "held"
    assert judge.judge_memory({}, {"tiny": None})["status"] == "inconclusive"
    assert judge.judge_connectivity({"offline_required": True}, {"offline": True, "network_attempts": 0})["status"] == "held"
    conn = judge.judge_connectivity({"offline_required": True}, {"offline": True, "network_attempts": 2}, {"offline": True})
    assert conn["status"] == "raised" and conn["meets_policy"] is False


@pytest.mark.parametrize("statuses, outcome", [
    (["held", "held"], "held"),
    (["lowered", "held"], "inclusive"),
    (["raised", "held"], "raised"),
    (["raised", "lowered"], "trade-off"),
    (["inconclusive", "lowered"], "inconclusive"),
])
def test_pareto(statuses, outcome):
    assert judge.pareto({str(i): {"status": s} for i, s in enumerate(statuses)}) == outcome


def test_gate_decision():
    held = {"cpu": {"status": "held", "meets_policy": True}}
    raised = {"cpu": {"status": "raised", "meets_policy": False}}
    assert judge.decide(held)["decision"] == "pass"
    assert judge.decide(raised)["decision"] == "fail"
    assert judge.decide(raised, ["cpu"])["decision"] == "pass-with-notice"
    assert judge.decide({"cpu": {"status": "inconclusive", "meets_policy": None}}, ["cpu"])["decision"] == "fail"


def test_judge_release(doc):
    result = judge.judge(doc, scan=scan("x86-64-v3"), previous={"cpu": {"x86_64": "x86-64-v3"}},
                         connectivity={"offline": True, "network_attempts": 0})
    assert result["floors"]["cpu"]["status"] == "held"
    assert result["floors"]["cpu"]["meets_policy"] is False
    assert result["unmeasured"] == ["memory"]
    assert result["decision"] == "fail" and result["missing_notice"] == ["cpu"]


def test_cli_policy(capsys, tmp_path):
    assert main(["policy"]) == 0
    assert "valid" in capsys.readouterr().out
    bad = tmp_path / "bad.yml"
    bad.write_text("version: 2\n", encoding="utf-8")
    assert main(["policy", str(bad)]) == 1


def test_cli_judge(tmp_path, capsys):
    import json
    path = tmp_path / "scan.json"
    path.write_text(json.dumps({"summary": scan("x86-64-v1")}), encoding="utf-8")
    out = tmp_path / "judge.json"
    assert main(["judge", "--scan", str(path), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["decision"] == "pass"
    assert "Decision: pass" in capsys.readouterr().out
