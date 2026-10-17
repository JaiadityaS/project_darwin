import copy
import json
import math

import yaml

from floor import footprint, manifest
from floor.cli import main

ENERGY = {
    "measured_at": "2026-10-16T10:00:00Z", "vcpus": 2, "cpu_model": "AMD EPYC 7763 64-Core Processor",
    "runs_per_build": 5, "audio_minutes": 2.2, "evidence": "https://example.test/runs/1",
    "builds": {"all-variants": {"wall_s": 30.0, "cpu_s": 58.0, "peak_rss_mb": 300.0},
               "native": {"wall_s": 20.0, "cpu_s": 39.0, "peak_rss_mb": 290.0},
               "broken": {"result": "fail"}},
}
METER = {"measured_at": "2026-10-16T10:00:00Z", "wall_s": 600.0, "vcpus": 2, "cpu_s": 900.0, "memory_gb_s": 1800.0,
         "cpu_model": "AMD EPYC 9V74 80-Core Processor"}


def if_run(doc: dict) -> dict:
    """A small copy of if-run for the builtins that the manifests use."""
    plugins = doc["initialize"]["plugins"]
    out = copy.deepcopy(doc)
    for child in out["tree"]["children"].values():
        rows = []
        for obs in child["inputs"]:
            row = {**child.get("defaults", {}), **obs}
            for name in child["pipeline"]["compute"]:
                method, config = plugins[name]["method"], plugins[name]["config"]
                if method == "Multiply":
                    row[config["output-parameter"]] = math.prod(row[k] for k in config["input-parameters"])
                elif method == "Sum":
                    row[config["output-parameter"]] = sum(row[k] for k in config["input-parameters"])
                elif method == "Subtract":
                    first, *rest = config["input-parameters"]
                    row[config["output-parameter"]] = row[first] - sum(row[k] for k in rest)
                elif method == "Divide":
                    d = config["denominator"]
                    row[config["output"]] = row[config["numerator"]] / (d if isinstance(d, (int, float)) else row[d])
                elif method == "SciEmbodied":
                    row["embodied-carbon"] = (config["baseline-emissions"] * row.get("usage-ratio", 1)
                                              * row["duration"] / config["lifespan"])
                elif method == "Sci":
                    row["sci"] = row["carbon"] / row[config["functional-unit"]]
                else:
                    raise AssertionError(method)
            rows.append(row)
        child["outputs"] = rows
    out["execution"] = {"status": "success"}
    return out


def _docs():
    files = footprint.write(footprint.load(), ENERGY, METER)
    return {name: yaml.safe_load(text) for name, text in files.items()}


def test_microarchitecture():
    assert footprint.microarchitecture("AMD EPYC 7763 64-Core Processor") == "EPYC 3rd Gen"
    assert footprint.microarchitecture("AMD EPYC 9V74 80-Core Processor") == "EPYC 4th Gen"
    assert footprint.microarchitecture("AMD EPYC 7B12") == "EPYC 2nd Gen"
    assert footprint.microarchitecture("Intel(R) Xeon(R) Platinum 8272CL CPU @ 2.60GHz") == "Cascade Lake"
    assert footprint.microarchitecture("Intel(R) Xeon(R) Platinum 8370C CPU @ 2.80GHz") == "Ice Lake"
    assert footprint.microarchitecture("Intel(R) Xeon(R) Platinum 8171M CPU @ 2.60GHz") == "Skylake"
    assert footprint.microarchitecture("Intel(R) Xeon(R) CPU E5-2673 v4 @ 2.30GHz") == "Broadwell"
    assert footprint.microarchitecture("Intel(R) Xeon(R) CPU @ 2.20GHz") is None
    assert footprint.microarchitecture("INTEL(R) XEON(R) PLATINUM 8581C CPU @ 2.10GHz") == "Emerald Rapids"  # GitLab
    watts, label = footprint.watts_for(footprint.load(), "Apple M2", "gcp")
    assert watts == {"min": 0.71, "max": 4.26} and "average" in label


def test_energy_formula():
    wh = footprint.energy_wh(60, 30, 100, {"min": 1, "max": 3}, 0.392, 1.1)
    assert math.isclose(wh, (60 * 1 + 30 * 2 + 100 * 0.392) * 1.1 / 3600)


def test_write_gives_one_child_per_measured_build():
    docs = _docs()
    assert set(docs) == {"sci-audio-minute.yml", "sci-release-check.yml"}
    audio = docs["sci-audio-minute.yml"]["tree"]["children"]
    assert list(audio) == ["all-variants", "native", "all-variants-us-central1"]  # 'broken' has no times
    assert audio["all-variants"]["defaults"]["grid/carbon-intensity"] == 11.36
    assert audio["all-variants-us-central1"]["defaults"]["grid/carbon-intensity"] == 431.95
    assert audio["all-variants"]["inputs"][0]["memory/gb-seconds"] == round(300 / 1024 * 30, 3)
    assert docs["sci-release-check.yml"]["tree"]["children"]["release-check"]["inputs"][0]["release-checks"] == 1
    assert footprint.write(footprint.load()) == {}


def test_release_check_watts_come_from_the_metered_cpu():
    config = footprint.load()
    check = _docs()["sci-release-check.yml"]
    defaults = check["tree"]["children"]["release-check"]["defaults"]
    row = config["watts_per_vcpu"]["microarchitecture"]["EPYC 4th Gen"]  # METER ran on an EPYC 9V74
    assert (defaults["cpu/watts-min"], defaults["cpu/watts-max"]) == (row["min"], row["max"])
    assert "Watts: EPYC 4th Gen" in check["description"] and "one job" in check["description"]
    joined = {**METER, "cpu_model": None, "scope": "cgroup", "jobs": {"scan": {}, "probe-qemu64": {}}}
    doc = yaml.safe_load(footprint.write(config, meter=joined)["sci-release-check.yml"])
    assert doc["tree"]["children"]["release-check"]["defaults"]["cpu/watts-min"] == 0.71  # the GCP average
    assert "the cgroup of each job container), the sum of 2 jobs (scan, probe-qemu64)" in doc["description"]


def test_check_accepts_correct_outputs_and_gives_sci():
    rows = []
    for name, doc in _docs().items():
        found, problems = footprint.check(if_run(doc), name)
        assert problems == []
        rows += found
    head = next(r for r in rows if r["child"] == "all-variants")
    energy_kwh = (60 * 0.71 + 58 * (4.26 - 0.71) + round(300 / 1024 * 30, 3) * 0.392) * 1.1 / 3600 / 1000
    embodied = 2321460 * 2 / 224 * 30 / 126144000
    assert math.isclose(head["sci_gco2e"], (energy_kwh * 11.36 + embodied) / 2.2, rel_tol=1e-12)
    assert head["headline"] and head["region"] == "northamerica-northeast1"
    far = next(r for r in rows if r["child"] == "all-variants-us-central1")
    assert far["sci_gco2e"] > 5 * head["sci_gco2e"]  # lever 5: the region
    summary = footprint.summarize(rows)
    assert summary["sci_gco2e_per_audio_minute"] == head["sci_gco2e"]
    assert summary["sci_gco2e_per_release_check"] > 0
    assert footprint.differences(summary, copy.deepcopy(summary)) == []


def test_check_finds_wrong_outputs():
    doc = if_run(_docs()["sci-audio-minute.yml"])
    doc["tree"]["children"]["native"]["outputs"][0]["sci"] *= 1.01
    del doc["tree"]["children"]["all-variants"]["outputs"][0]["carbon"]
    doc["execution"] = {"status": "fail", "error": "boom"}
    _, problems = footprint.check(doc, "x")
    assert any("native: sci" in p for p in problems)
    assert any("all-variants: missing input carbon" in p or "all-variants: carbon" in p for p in problems)
    assert any("status fail" in p for p in problems)
    _, problems = footprint.check(_docs()["sci-audio-minute.yml"], "x")
    assert any("no outputs" in p for p in problems)


def test_stale(tmp_path):
    files = footprint.write(footprint.load(), ENERGY, METER)
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    assert footprint.stale(files, tmp_path) == []
    (tmp_path / "sci-old.yml").write_text("x", encoding="utf-8")
    (tmp_path / "sci-release-check.yml").write_text("changed", encoding="utf-8")
    assert len(footprint.stale(files, tmp_path)) == 2


def test_committed_manifests_match_the_evidence():
    energy = json.loads(footprint.ENERGY_FILE.read_text("utf-8")) if footprint.ENERGY_FILE.exists() else None
    meter = json.loads(footprint.METER_FILE.read_text("utf-8")) if footprint.METER_FILE.exists() else None
    assert footprint.stale(footprint.write(footprint.load(), energy, meter), footprint.IMPACT_DIR) == []


def test_cli_write_check_and_manifest(tmp_path, capsys):
    (tmp_path / "e.json").write_text(json.dumps(ENERGY), encoding="utf-8")
    (tmp_path / "m.json").write_text(json.dumps(METER), encoding="utf-8")
    src, out = tmp_path / "src", tmp_path / "out"
    assert main(["footprint", "write", "--energy", str(tmp_path / "e.json"), "--meter", str(tmp_path / "m.json"),
                 "--out-dir", str(src)]) == 0
    assert main(["footprint", "stale", "--energy", str(tmp_path / "e.json"), "--meter", str(tmp_path / "m.json"),
                 "--out-dir", str(src)]) == 0
    out.mkdir()
    for path in src.glob("sci-*.yml"):
        (out / f"{path.stem}.yaml").write_text(yaml.safe_dump(if_run(yaml.safe_load(path.read_text("utf-8")))),
                                               encoding="utf-8")
    outputs = [str(p) for p in sorted(out.glob("*.yaml"))]
    assert main(["footprint", "check", *outputs, "--out", str(tmp_path / "sci.json")]) == 0
    assert main(["footprint", "check", *outputs, "--expect", str(tmp_path / "sci.json")]) == 0
    assert main(["footprint", "check", outputs[0], "--expect", str(tmp_path / "sci.json")]) == 1
    assert "every output matches" in capsys.readouterr().out
    summary = json.loads((tmp_path / "sci.json").read_text("utf-8"))
    verdict = {"floors": {"cpu": {"x86_64": "x86-64-v1", "status": "held"}}, "decision": "pass", "pareto": "held"}
    doc = manifest.build(verdict, subject="s", digest="sha256:00", release="r", commit="c", footprint=summary)
    assert doc["predicate"]["footprint"]["sci_gco2e_per_audio_minute"] == summary["sci_gco2e_per_audio_minute"]
    assert "Impact Framework" in doc["predicate"]["footprint"]["method"]
