import json

from floor import judge, manifest, policy
from floor.cli import main

POLICY = policy.load()


def scan(level):
    return {"floor": {"level": level, "extras": [], "sources": []}, "files": {"errors": []},
            "highest_level_found": "x86-64-v4", "baseline_variant": "x64"}


def release(level, previous=None, tag="v1-floor.1"):
    verdict = judge.judge(POLICY, scan=scan(level),
                          previous=(previous or {}).get("predicate", {}).get("floors"))
    return manifest.build(verdict, subject="registry.example/whisper.cpp/server", digest="sha256:" + "a" * 64,
                          release=tag, commit="0c7be69", scan=scan(level), previous=previous,
                          evidence="https://ci.example/job/1", fixed_by="fallback", project_url="https://example.org/p")


def test_statement_shape():
    doc = release("x86-64-v1")
    assert doc["_type"] == "https://in-toto.io/Statement/v1"
    assert doc["subject"][0]["digest"] == {"sha256": "a" * 64}
    assert doc["predicateType"] == "https://example.org/p/floor-manifest/v0.3"
    pred = doc["predicate"]
    assert pred["floors"]["cpu"]["x86_64"] == "x86-64-v1"
    assert pred["floors"]["cpu"]["evidence"] == "https://ci.example/job/1"
    assert pred["build"]["highest_level_found"] == "x86-64-v4"
    assert {"arm64", "memory", "connectivity", "language"} <= set(pred["unmeasured"])
    assert pred["diff_from"] is None
    assert pred["changes"] == []
    assert pred["delta_m_kgco2e"]["high"] == 0


def test_predicate_type_without_url(monkeypatch):
    monkeypatch.delenv("CI_PROJECT_URL", raising=False)
    assert manifest.predicate_type() == "urn:floor:floor-manifest:v0.3"


def test_diff_between_two_releases():
    old = release("x86-64-v3", tag="v1-floor.1")
    new = release("x86-64-v1", previous=old, tag="v2-floor.1")
    pred = new["predicate"]
    assert pred["diff_from"] == "v1-floor.1"
    assert pred["changes"] == [{"dimension": "cpu", "from": "x86-64-v3", "to": "x86-64-v1", "status": "lowered",
                                "fixed_by": "fallback"}]
    text = manifest.diff_markdown(old, new)
    assert "| cpu | x86-64-v3 | x86-64-v1 | lowered |" in text
    assert "cpu: x86-64-v3 → x86-64-v1 (lowered)" in text


def test_raise_needs_a_scenario():
    old = release("x86-64-v1")
    new = release("x86-64-v3", previous=old)
    assert new["predicate"]["changes"][0]["status"] == "raised"
    assert "fixed_by" not in new["predicate"]["changes"][0]
    assert new["predicate"]["delta_m_kgco2e"]["high"] is None
    assert "No floor moved." in manifest.diff_markdown(old, release("x86-64-v1", previous=old))


def test_cli_manifest_and_diff(tmp_path, capsys):
    scan_file = tmp_path / "scan.json"
    scan_file.write_text(json.dumps({"summary": scan("x86-64-v1")}), encoding="utf-8")
    verdict = tmp_path / "judge.json"
    assert main(["judge", "--scan", str(scan_file), "--out", str(verdict)]) == 0
    first, second = tmp_path / "m1.json", tmp_path / "m2.json"
    common = ["--judge", str(verdict), "--subject", "img", "--digest", "sha256:" + "b" * 64, "--commit", "abc",
              "--scan", str(scan_file)]
    assert main(["manifest", *common, "--release", "r1", "--out", str(first)]) == 0
    assert main(["judge", "--scan", str(scan_file), "--previous", str(first), "--out", str(verdict)]) == 0
    diff = tmp_path / "diff.md"
    assert main(["manifest", *common, "--release", "r2", "--previous", str(first), "--out", str(second),
                 "--diff", str(diff)]) == 0
    assert json.loads(second.read_text(encoding="utf-8"))["predicate"]["diff_from"] == "r1"
    assert "r1 → r2" in diff.read_text(encoding="utf-8")
    capsys.readouterr()
    assert main(["diff", str(first), str(second)]) == 0
    assert "No floor moved." in capsys.readouterr().out
