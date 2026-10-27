"""D-040: Cloud Run from the held, signed image (F13.1), with staging, a smoke test and rollback (F13.2)."""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CI = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
TF = (ROOT / "infra" / "main.tf").read_text(encoding="utf-8")
RULE = [{"if": "$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH && $GCP_PROJECT_ID"}]


def test_deploy_jobs_run_only_for_a_signed_image_on_main():
    image, deploy = CI["deploy-image"], CI["deploy"]
    assert CI["stages"][-1] == "deploy" and image["stage"] == deploy["stage"] == "deploy"
    assert image["needs"] == ["build", "attest"] and deploy["needs"] == ["deploy-image"]
    assert image["rules"] == deploy["rules"] == RULE
    assert CI["variables"]["GCP_PROJECT_ID"] == ""  # off until infra/ is applied
    assert CI["variables"]["GCP_REGION"] == "northamerica-northeast1"
    for job in (image, deploy):
        assert job["id_tokens"] == {"GCP_ID_TOKEN": {"aud": "$GCP_WIF_AUDIENCE"}}
        assert job["interruptible"] is False
        script = job["script"][0]
        assert "sh .gitlab/ci/gcp-token.sh /tmp/gcp-token" in script
        assert "GOOGLE_APPLICATION_CREDENTIALS" not in script and "keys create" not in script
    assert '-f deploy/service.Dockerfile --build-arg IMAGE="$IMAGE_REF"' in image["script"][0]
    assert image["artifacts"]["reports"]["dotenv"] == "out/deploy/image.env"
    assert deploy["resource_group"] == "cloud-run"


def test_production_gets_traffic_only_after_the_smoke_test():
    script = CI["deploy"]["script"][0]
    staging = script.index('--image "$SERVICE_IMAGE" --no-traffic --tag candidate')
    checks = [script.index(s) for s in (
        '"$candidate/healthz"', '--data-binary @samples/jfk.wav "$candidate/transcribe"',
        'grep -qi "$EXPECT" out/deploy/transcribe.json', '"$candidate/floor"',
        '[ "$code" = 400 ]')]
    production = script.index("update-traffic rieux")
    assert staging < min(checks) and max(checks) < production
    assert "--to-tags candidate=100" in script
    assert script.index("out/deploy/url.txt") > production


def test_infra_limits_and_identity():
    assert 'default     = "northamerica-northeast1"' in TF
    assert "min_instance_count = 0" in TF and "max_instance_count = 1" in TF
    assert ("attribute_condition = \"assertion.project_id == '${var.gitlab_project_id}' && "
            "assertion.ref_type == 'branch' && assertion.ref == '${var.gitlab_branch}'\"") in TF
    assert 'default     = "87296266"' in TF and 'default     = "main"' in TF
    assert 'issuer_uri = "https://gitlab.com"' in TF
    assert "google_service_account_key" not in TF  # no key file
    assert TF.count('member   = "allUsers"') == 1 and 'role     = "roles/run.invoker"' in TF
    # The deploy jobs own the image and the traffic.
    assert "template[0].containers[0].image" in TF and "      traffic,\n" in TF
    for name in ("GCP_PROJECT_ID", "GCP_REGION", "GCP_WIF_PROVIDER", "GCP_WIF_AUDIENCE", "GCP_SERVICE_ACCOUNT"):
        assert f"{name} " in TF and name in CI["variables"]


FAKE_CURL = """#!/bin/sh
for a in "$@"; do
  case "$a" in
    https://sts.googleapis.com/*) printf '{\\n "access_token": "FEDERATED-123",\\n "token_type": "Bearer"\\n}\\n'; exit 0 ;;
    https://iamcredentials.googleapis.com/*) printf '{\\n  "accessToken": "ACCESS-456",\\n  "expireTime": "x"\\n}\\n'; exit 0 ;;
  esac
done
exit 22
"""


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_token_script_writes_the_token_and_never_prints_it(tmp_path):
    curl = tmp_path / "bin" / "curl"
    curl.parent.mkdir()
    curl.write_text(FAKE_CURL)
    curl.chmod(curl.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ, PATH=f"{curl.parent}{os.pathsep}{os.environ['PATH']}", GCP_ID_TOKEN="JWT-789",
               GCP_WIF_PROVIDER="projects/1/locations/global/workloadIdentityPools/p/providers/g",
               GCP_SERVICE_ACCOUNT="rieux-deploy@x.iam.gserviceaccount.com")
    out = tmp_path / "token"
    run = subprocess.run(["sh", str(ROOT / ".gitlab/ci/gcp-token.sh"), str(out)],
                         env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert out.read_text().strip() == "ACCESS-456"
    for secret in ("FEDERATED-123", "ACCESS-456", "JWT-789"):
        assert secret not in run.stdout + run.stderr
    env["GCP_WIF_PROVIDER"] = ""
    assert subprocess.run(["sh", str(ROOT / ".gitlab/ci/gcp-token.sh"), str(out)],
                          env=env, capture_output=True, text=True).returncode != 0
