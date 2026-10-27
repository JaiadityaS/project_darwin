#!/usr/bin/env bash
# Deploys the Rieux service to Cloud Run from Cloud Shell, with gcloud only (no OpenTofu state).
# It deploys the image that the gate held for release v1.9.5-rieux.1-floor.1 (merge commit ccd4f10d,
# main pipeline 2987186947, whose `service` job ran this same recipe on this image and passed).
# Usage, in Cloud Shell:  bash quick-deploy.sh [PROJECT_ID]
set -euo pipefail

PROJECT="${1:-$(gcloud config get-value project 2> /dev/null)}"
[ -n "$PROJECT" ] || { echo "usage: bash quick-deploy.sh PROJECT_ID"; exit 2; }
REGION="${REGION:-northamerica-northeast1}"
SRC="https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase/-/raw/main"
HELD="registry.gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase/main@sha256:5ff92d99a96e9d752b14619e216fcfc522d0cdf9533d64108e915774517ad3af"
EXPECT="ask not what your country can do for you"
REGISTRY="$REGION-docker.pkg.dev"
IMAGE="$REGISTRY/$PROJECT/rieux/service:floor-1"

step() { echo; echo "== $*"; }
retry() { local n; for n in 1 2 3 4 5; do "$@" && return 0; echo "retry $n in 20 s: $*"; sleep 20; done; return 1; }

step "project $PROJECT, region $REGION"
gcloud config set project "$PROJECT" > /dev/null
if [ "$(gcloud billing projects describe "$PROJECT" --format 'value(billingEnabled)' 2> /dev/null)" = "False" ]; then
  echo "billing is not enabled for $PROJECT. Link a billing account, then run again."; exit 1
fi

step "APIs"
retry gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

step "Artifact Registry repository rieux"
gcloud artifacts repositories describe rieux --location "$REGION" > /dev/null 2>&1 \
  || retry gcloud artifacts repositories create rieux --repository-format docker --location "$REGION"

step "build context from the public GitLab project"
work="$(mktemp -d)"
for f in deploy/service.Dockerfile .floor/floor/gateway.py .floor/floor/gateway.html samples/jfk.wav; do
  mkdir -p "$work/$(dirname "$f")"
  curl -fsSL --retry 3 -o "$work/$f" "$SRC/$f"
done

step "build and push $IMAGE"
if docker info > /dev/null 2>&1; then
  gcloud auth configure-docker "$REGISTRY" --quiet > /dev/null
  docker build -f "$work/deploy/service.Dockerfile" --build-arg IMAGE="$HELD" -t "$IMAGE" "$work"
  retry docker push "$IMAGE"
else
  cat > "$work/cloudbuild.yaml" << EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args: [build, -f, deploy/service.Dockerfile, --build-arg, IMAGE=$HELD, -t, $IMAGE, .]
images: [$IMAGE]
EOF
  gcloud builds submit "$work" --config "$work/cloudbuild.yaml"
fi

step "deploy the Cloud Run service rieux"
retry gcloud run deploy rieux --image "$IMAGE" --region "$REGION" --allow-unauthenticated --quiet \
  --port 8080 --cpu 1 --memory 2Gi --min-instances 0 --max-instances 1 --concurrency 8 \
  --timeout 120 --cpu-boost --execution-environment gen2
gcloud run services add-iam-policy-binding rieux --region "$REGION" \
  --member allUsers --role roles/run.invoker --quiet > /dev/null

url="$(gcloud run services describe rieux --region "$REGION" --format 'value(status.url)')"
echo "service: $url"

step "smoke test"
# Cloud Run reserves paths that end in "z" (such as /healthz) at its front end, so probe the page.
ok=0
for i in $(seq 1 30); do
  if curl -fsS -o /dev/null --max-time 20 "$url/"; then ok=1; break; fi
  sleep 10
done
[ "$ok" = 1 ] || { echo "FAIL: the page never answered. Logs: gcloud run services logs read rieux --region $REGION"; exit 1; }
code=$(curl -sS -o "$work/transcribe.json" -w '%{http_code}' --max-time 120 -H "Content-Type: audio/wav" \
  --data-binary @"$work/samples/jfk.wav" "$url/transcribe")
cat "$work/transcribe.json"; echo
[ "$code" = 200 ] && grep -qi "$EXPECT" "$work/transcribe.json" || { echo "FAIL: transcribe gave HTTP $code"; exit 1; }
curl -fsS --max-time 20 "$url/floor"; echo
echo "smoke test: pass"
echo "URL: $url"
