import base64
import json
from pathlib import Path

import pytest

from floor import attest, judge, manifest, policy
from floor.cli import main

ROOT = Path(__file__).resolve().parents[2]


def statement():
    scan = {"floor": {"level": "x86-64-v1", "extras": [], "sources": []}, "files": {"errors": []},
            "highest_level_found": "x86-64-v4", "baseline_variant": "x64"}
    verdict = judge.judge(policy.load(), scan=scan)
    return manifest.build(verdict, subject="registry.example/g/p/main", digest="sha256:" + "b" * 64,
                          release="main-0c7be69", commit="0c7be69", scan=scan, project_url="https://example.org/p")


def envelope(doc: dict) -> str:
    """One line of cosign verify-attestation output: a DSSE envelope with the Statement as its payload."""
    payload = base64.b64encode(json.dumps(doc).encode()).decode()
    return json.dumps({"payloadType": attest.PAYLOAD_TYPE, "payload": payload, "signatures": [{"sig": "x"}]})


def signed(doc: dict) -> dict:
    """What cosign signs: its own Statement (v0.1) around the predicate, on the same digest."""
    kind, pred = attest.predicate(doc)
    return {"_type": "https://in-toto.io/Statement/v0.1", "predicateType": kind,
            "subject": [{"name": "registry.example/g/p/main", "digest": {"sha256": "b" * 64}}], "predicate": pred}


def token(claims: dict) -> str:
    part = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"eyJhbGciOiJSUzI1NiJ9.{part}.c2ln"


def test_predicate_split():
    kind, pred = attest.predicate(statement())
    assert kind == "https://example.org/p/floor-manifest/v0.3"
    assert pred["floors"]["cpu"]["x86_64"] == "x86-64-v1" and "subject" not in pred
    with pytest.raises(ValueError):
        attest.predicate({"floors": {}})  # a judge output is not a manifest


def test_identity_reads_one_claim():
    claims = {"ci_config_ref_uri": "gitlab.com/g/p//.gitlab-ci.yml@refs/heads/main", "user_login": "someone"}
    assert attest.identity(token(claims)) == "https://gitlab.com/g/p//.gitlab-ci.yml@refs/heads/main"
    with pytest.raises(ValueError, match="no ci_config_ref_uri"):
        attest.identity(token({"sub": "project_path:g/p:ref_type:branch:ref:main"}))
    with pytest.raises(ValueError, match="not a JWT"):
        attest.identity("not-a-token")


def test_check():
    doc = statement()
    good = signed(doc)
    assert attest.check(doc, envelope(good) + "\n") is None
    assert attest.check(doc, "") == "cosign verified no in-toto attestation"
    other_digest = {**good, "subject": [{"name": "x", "digest": {"sha256": "c" * 64}}]}
    assert "no verified attestation" in attest.check(doc, envelope(other_digest))
    changed = json.loads(json.dumps(good))
    changed["predicate"]["floors"]["cpu"]["x86_64"] = "x86-64-v3"
    assert "different predicate" in attest.check(doc, envelope(changed))
    # A second, older attestation of the same image does not hide the matching one.
    assert attest.check(doc, envelope(changed) + "\n" + envelope(good)) is None


def test_cli(tmp_path, monkeypatch, capsys):
    path = tmp_path / "floor-manifest.json"
    path.write_text(json.dumps(statement()), encoding="utf-8")
    pred = tmp_path / "predicate.json"
    assert main(["attest", "predicate", "--manifest", str(path), "--out", str(pred)]) == 0
    assert capsys.readouterr().out.strip() == "https://example.org/p/floor-manifest/v0.3"
    assert json.loads(pred.read_text(encoding="utf-8")) == statement()["predicate"]

    monkeypatch.setenv("SIGSTORE_ID_TOKEN", token({"ci_config_ref_uri": "gitlab.com/g/p//.gitlab-ci.yml@refs/tags/v1"}))
    assert main(["attest", "identity"]) == 0
    assert capsys.readouterr().out.strip() == "https://gitlab.com/g/p//.gitlab-ci.yml@refs/tags/v1"
    monkeypatch.delenv("SIGSTORE_ID_TOKEN")
    assert main(["attest", "identity"]) == 2

    verified = tmp_path / "verified.jsonl"
    verified.write_text(envelope(signed(statement())) + "\n", encoding="utf-8")
    assert main(["attest", "check", "--manifest", str(path), "--verified", str(verified)]) == 0
    assert "attestation: verified" in capsys.readouterr().out
    verified.write_text("", encoding="utf-8")
    assert main(["attest", "check", "--manifest", str(path), "--verified", str(verified)]) == 1


def test_attest_ci_job():
    """F5.4, D-023: only after a passed judge; keyless; verified with the exact identity; a pinned cosign."""
    import yaml
    ci = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    job = ci["attest"]
    assert job["stage"] == "publish" and job["needs"] == ["build", "judge"]
    assert "when" not in job and "rules" not in job and "allow_failure" not in job  # runs only when the judge passed
    assert job["id_tokens"] == {"SIGSTORE_ID_TOKEN": {"aud": "sigstore"}}
    assert len(job["variables"]["COSIGN_SHA256"]) == 64 and job["variables"]["COSIGN_VERSION"].startswith("2.")
    script = "\n".join(job["script"])
    assert 'echo "$COSIGN_SHA256  /usr/local/bin/cosign" | sha256sum -c -' in script
    assert script.index("sha256sum -c -") < script.index("chmod +x /usr/local/bin/cosign")
    assert 'cosign attest --yes --type "$type" --predicate out/attest/predicate.json "$IMAGE_REF"' in script
    assert '--certificate-identity "$identity"' in script and '--certificate-oidc-issuer "$CI_SERVER_URL"' in script
    assert "floor attest check --manifest out/judge/floor-manifest.json --verified out/attest/verified.jsonl" in script
    assert "--certificate-identity-regexp" not in script and "SIGSTORE_ID_TOKEN" not in script  # no echo of the token
    assert job["artifacts"]["paths"] == ["out/attest/"]
