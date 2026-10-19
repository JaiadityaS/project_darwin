import json
from pathlib import Path

import pytest

from floor import herald
from floor.cli import main

ROOT = Path(__file__).resolve().parents[2]


def statement(cpu_level="x86-64-v1", status="held", dispatch=None, notices=()):
    return {"_type": "https://in-toto.io/Statement/v1", "predicate": {
        "release": "v1.8.2-floor.1", "commit": "0c7be696371069e0",
        "floors": {
            "cpu": {"status": status, "x86_64": cpu_level, "proof": "static",
                    "dispatch": dispatch if dispatch is not None else
                    {"qemu64": "x64", "Nehalem": "sse42", "SandyBridge": "sandybridge", "EPYC-Milan": "zen4"}},
            "memory": {"status": "held", "smallest_passing_mb": {"small": 768, "tiny": 512, "base": 512}},
            "connectivity": {"status": "held", "offline": "proven", "network_attempts": 0, "download_mb": 81.9}},
        "unmeasured": ["arm64", "gpu-backends", "language"],
        "leave_behind_notices": list(notices),
        "footprint": {"sci_gco2e_per_audio_minute": 0.0019596936511420246}}}


def test_who_for_a_held_release():
    text = herald.who(statement())
    assert text.startswith("## Who this release serves\n")
    assert "`v1.8.2-floor.1` (commit `0c7be696`)" in text
    assert "any 64-bit x86 PC" in text and "(floor `x86-64-v1`, held, static proof of every ELF file)" in text
    assert "ran on qemu64 (a generic x86-64 CPU: `x64`), Nehalem (Intel, 2008: `sse42`)" in text
    assert "did not run" not in text
    assert "tiny in 512 MB, base in 512 MB, small in 768 MB" in text  # model order, not key order
    assert "one download of 81.9 MB" in text and "0 network attempts" in text
    assert "nobody: this release has no Leave-Behind Notice" in text
    assert "Arm CPUs, GPU backends, languages other than English" in text
    assert "0.00196 g CO2e per audio-minute" in text


def test_who_never_hides_a_raise():
    text = herald.who(statement("x86-64-v4", "raised", {m: None for m in herald.MODELS}))
    assert "AVX-512" in text and "It did not run on qemu64" in text and "ran on" not in text
    assert "the cpu floor rose and no notice allows it" in text and "nobody" not in text
    notice = herald.who(statement(notices=["notice-0001 (Nehalem class)"]))
    assert "notice-0001 (Nehalem class) (Leave-Behind Notice)." in notice


def test_cli(tmp_path, capsys):
    path = tmp_path / "floor-manifest.json"
    path.write_text(json.dumps(statement()), encoding="utf-8")
    out = tmp_path / "out" / "who.md"
    assert main(["herald", "--manifest", str(path), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == capsys.readouterr().out == herald.who(statement())


def test_herald_ci_job():
    """F12.1, D-025: after attest, from the manifest; the release notes carry it."""
    import yaml
    ci = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    job = ci["herald"]
    assert job["needs"] == ["judge", "attest"] and job["artifacts"]["paths"] == ["out/herald/"]
    assert "floor herald --manifest out/judge/floor-manifest.json --out out/herald/who.md" in job["script"]
    assert "herald" in ci["release"]["needs"] and "--herald out/herald/who.md" in "\n".join(ci["release"]["script"])



def signed(**kw):
    doc = statement(**kw)
    doc["subject"] = [{"name": "registry.gitlab.com/x/main", "digest": {"sha256": "9023193a1b3aa22458899b22"}}]
    doc["predicate"].update(decision="pass", pareto="held")
    return doc


def test_summary_is_short_and_copies_who():
    """F12.3, D-032: at most 7 lines (the flow adds the tag line), every value from the manifest or who.md."""
    doc = signed()
    who = herald.who(doc)
    text = herald.summary(doc, who)
    lines = text.splitlines()
    assert len(lines) <= herald.SUMMARY_MAX_LINES and text.endswith("\n")
    assert lines[0] == ("**Rieux gate pass** for commit `0c7be696` (image `sha256:9023193a1b3a`), Pareto held. "
                        "SCI 0.00196 g CO2e per audio-minute.")
    assert lines[1] == "- CPU: floor `x86-64-v1`, held (static proof); ran on 4 of 4 emulated CPU models."
    assert lines[2] == "- Memory: held; tiny 512 MB, base 512 MB, small 768 MB."
    assert lines[3] == "- Connectivity: held; offline proven, 81.9 MB download, 0 network attempts."
    for label in ("Left behind", "Not measured"):  # copied from who.md as it is
        assert [line for line in who.splitlines() if line.startswith(f"- **{label}:**")][0] in lines


def test_summary_never_hides_a_raise_and_keeps_the_limit(monkeypatch):
    doc = signed(cpu_level="x86-64-v4", status="raised", dispatch={m: None for m in herald.MODELS})
    doc["predicate"]["floors"]["language"] = {"served": ["en", "es"], "not_served": ["sw"]}
    text = herald.summary(doc, herald.who(doc))
    assert "- CPU: floor `x86-64-v4`, raised (static proof); ran on 0 of 4 emulated CPU models." in text
    assert "the cpu floor rose and no notice allows it" in text and "- **Language:** served: en, es." in text
    assert len(text.splitlines()) == herald.SUMMARY_MAX_LINES  # every optional line is there
    del doc["predicate"]["floors"]["connectivity"]["download_mb"]  # older manifests have no size
    assert "- Connectivity: held; offline proven, 0 network attempts." in herald.summary(doc, "")
    monkeypatch.setattr(herald, "SUMMARY_MAX_LINES", 6)
    with pytest.raises(ValueError, match="7 lines, more than 6"):
        herald.summary(doc, herald.who(doc))
    assert herald.summary(doc, "").count("\n") == 4  # no who.md lines: the manifest lines only


def test_summary_cli(tmp_path, capsys):
    manifest, who = tmp_path / "floor-manifest.json", tmp_path / "who.md"
    manifest.write_text(json.dumps(signed()), encoding="utf-8")
    who.write_text(herald.who(signed()), encoding="utf-8")
    out = tmp_path / "out" / "summary.md"
    assert main(["summary", "--manifest", str(manifest), "--who", str(who), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == capsys.readouterr().out == herald.summary(signed(), herald.who(signed()))
    assert main(["summary", "--manifest", str(manifest), "--who", str(tmp_path / "none.md")]) == 2


def test_herald_job_prints_the_summary():
    """D-032: the flow tools read job logs, not artifacts (D-021), so the log carries the summary and the issue."""
    import yaml
    ci = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    script = ci["herald"]["script"]
    assert ("floor summary --manifest out/judge/floor-manifest.json --who out/herald/who.md "
            "--out out/herald/summary.md > /dev/null") in script
    assert script[-2:] == ['echo "summary issue: $FLOOR_SUMMARY_ISSUE"',
                           'echo "--- BEGIN summary ---"; cat out/herald/summary.md; echo "--- END summary ---"']
    assert "FLOOR_SUMMARY_ISSUE" in ci["variables"]
