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


def test_diff_without_previous_release():
    text = manifest.diff_markdown(None, release("x86-64-v3"))
    assert "no previous release → v1-floor.1" in text
    assert "| cpu | - | x86-64-v3 | raised |" in text
    assert "the Judge compares each floor with the policy." in text
    assert "No floor moved." not in text


def test_floor_evidence_and_judge_notes():
    verdict = judge.judge(POLICY, scan=scan("x86-64-v1"), memory={"small": 768}, peak_rss={"small": 830},
                          model_download_mb={"small": 492.0},
                          connectivity={"offline": True, "network_attempts": 0, "download_mb": 81.9,
                                        "download_bytes": {"ggml-tiny.en.bin": 77704715}},
                          previous={"memory": {"smallest_passing_mb": {"small": 768}, "peak_rss_mb": {"small": 750}}})
    doc = manifest.build(verdict, subject="s", digest="sha256:" + "a" * 64, release="r", commit="c",
                         evidence="https://ci.example/pipelines/1",
                         floor_evidence={"memory": "https://ci.example/jobs/2", "connectivity": "https://ci.example/jobs/3"})
    floors = doc["predicate"]["floors"]
    assert floors["cpu"]["evidence"] == "https://ci.example/pipelines/1"
    assert floors["memory"]["evidence"] == "https://ci.example/jobs/2"
    assert floors["memory"]["smallest_passing_mb"] == {"small": 768} and floors["memory"]["peak_rss_mb"] == {"small": 830}
    assert floors["memory"]["download_mb"] == {"small": 492.0}
    assert floors["connectivity"]["evidence"] == "https://ci.example/jobs/3"
    assert floors["connectivity"]["offline"] == "proven" and floors["connectivity"]["download_mb"] == 81.9
    text = manifest.diff_markdown(None, doc)
    assert "Judge notes:\n- memory: small: peak RSS 830 MB, 10.7% more than 750 MB" in text


def test_cli_manifest_and_diff(tmp_path, capsys):
    scan_file = tmp_path / "scan.json"
    scan_file.write_text(json.dumps({"summary": scan("x86-64-v1")}), encoding="utf-8")
    verdict = tmp_path / "judge.json"
    assert main(["judge", "--scan", str(scan_file), "--out", str(verdict)]) == 0
    first, second = tmp_path / "m1.json", tmp_path / "m2.json"
    common = ["--judge", str(verdict), "--subject", "img", "--digest", "sha256:" + "b" * 64, "--commit", "abc",
              "--scan", str(scan_file)]
    assert main(["manifest", *common, "--release", "r1", "--build-cpu", "AMD EPYC 7B13", "--evidence", "https://ci/p/1",
                 "--floor-evidence", "cpu=https://ci/j/2", "--out", str(first)]) == 0
    predicate = json.loads(first.read_text(encoding="utf-8"))["predicate"]
    assert predicate["build"]["host_cpu"] == "AMD EPYC 7B13"
    assert predicate["floors"]["cpu"]["evidence"] == "https://ci/j/2"
    assert main(["manifest", *common, "--release", "r1", "--floor-evidence", "cpu", "--out", str(first)]) == 2
    assert main(["judge", "--scan", str(scan_file), "--previous", str(first), "--out", str(verdict)]) == 0
    diff = tmp_path / "diff.md"
    assert main(["manifest", *common, "--release", "r2", "--previous", str(first), "--out", str(second),
                 "--diff", str(diff)]) == 0
    assert json.loads(second.read_text(encoding="utf-8"))["predicate"]["diff_from"] == "r1"
    assert "r1 → r2" in diff.read_text(encoding="utf-8")
    capsys.readouterr()
    assert main(["diff", str(first), str(second)]) == 0
    assert "No floor moved." in capsys.readouterr().out


def test_judge_job_reads_the_committed_footprint(tmp_path):
    """T-54: the judge job passes the committed SCI summary, so the manifest's footprint fields are not null."""
    from pathlib import Path

    import yaml
    root = Path(__file__).resolve().parents[2]
    sci = root / ".floor/evidence/footprint/sci.json"
    script = "\n".join(yaml.safe_load((root / ".gitlab-ci.yml").read_text(encoding="utf-8"))["judge"]["script"])
    assert "sci=.floor/evidence/footprint/sci.json" in script and '--footprint "$sci"' in script
    scan_file = tmp_path / "scan.json"
    scan_file.write_text(json.dumps({"summary": scan("x86-64-v1")}), encoding="utf-8")
    verdict, out = tmp_path / "judge.json", tmp_path / "m.json"
    assert main(["judge", "--scan", str(scan_file), "--out", str(verdict)]) == 0
    assert main(["manifest", "--judge", str(verdict), "--subject", "img", "--digest", "sha256:" + "b" * 64,
                 "--commit", "abc", "--release", "r1", "--footprint", str(sci), "--out", str(out)]) == 0
    footprint = json.loads(out.read_text(encoding="utf-8"))["predicate"]["footprint"]
    assert footprint["sci_gco2e_per_audio_minute"] > 0 and footprint["sci_gco2e_per_release_check"] > 0
    assert footprint["method"].startswith("GSF Impact Framework")
