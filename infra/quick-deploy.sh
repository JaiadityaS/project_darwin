#!/usr/bin/env bash
# Deploys the Rieux service to Cloud Run from Cloud Shell, with gcloud only (no OpenTofu state).
# Use it when there is no time for main.tf and a main pipeline. It deploys the image that the gate
# held for release v1.9.5-rieux.1-floor.1 (merge commit ccd4f10d, main pipeline 2987186947).
# Usage, in Cloud Shell:  bash quick-deploy.sh PROJECT_ID
set -euo pipefail

PROJECT="${1:?usage: bash quick-deploy.sh PROJECT_ID}"
REGION="${REGION:-northamerica-northeast1}"
SRC="https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase/-/raw/main"
HELD="registry.gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase/main@sha256:5ff92d99a96e9d752b14619e216fcfc522d0cdf9533d64108e915774517ad3af"
EXPECT="ask not what your country can do for you"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/rieux/service:floor-1"

gcloud config set project "$PROJECT"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
gcloud artifacts repositories describe rieux --location "$REGION" > /dev/null 2>&1 \
  || gcloud artifacts repositories create rieux --repository-format docker --location "$REGION"

# The build context: the service recipe and the gateway, from the public GitLab project.
work="$(mktemp -d)"
mkdir -p "$work/deploy" "$work/.floor/floor"
for f in deploy/service.Dockerfile .floor/floor/gateway.py .floor/floor/gateway.html samples/jfk.wav; do
  mkdir -p "$work/$(dirname "$f")"
  curl -fsSL -o "$work/$f" "$SRC/$f"
done
cat > "$work/cloudbuild.yaml" <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args: [build, -f, deploy/service.Dockerfile, --build-arg, IMAGE=$HELD, -t, $IMAGE, .]
images: [$IMAGE]
EOF
gcloud builds submit "$work" --config "$work/cloudbuild.yaml"

gcloud run deploy rieux --image "$IMAGE" --region "$REGION" --allow-unauthenticated \
  --port 8080 --cpu 1 --memory 2Gi --min-instances 0 --max-instances 1 --concurrency 8 \
  --timeout 120 --cpu-boost

url="$(gcloud run services describe rieux --region "$REGION" --format 'value(status.url)')"
echo "service: $url"

# Smoke test: health, the JFK sample, the floor of the host.
for i in $(seq 1 30); do curl -fsS -o /dev/null --max-time 20 "$url/healthz" && break; sleep 10; done
curl -sS --max-time 120 -H "Content-Type: audio/wav" --data-binary @"$work/samples/jfk.wav" "$url/transcribe" | tee "$work/transcribe.json"; echo
grep -qi "$EXPECT" "$work/transcribe.json" && echo "smoke test: pass" || echo "smoke test: FAIL"
curl -sS --max-time 20 "$url/floor"; echo
echo "URL: $url"
