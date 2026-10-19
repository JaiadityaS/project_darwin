import json
from pathlib import Path

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
