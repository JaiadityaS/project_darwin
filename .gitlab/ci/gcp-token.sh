#!/bin/sh
# Workload Identity Federation (F13.1, D-040): trades this job's GitLab ID token for a short-lived
# Google access token of the deploy service account. No key file. It writes the token to a file
# that only this user can read, and it never prints a token.
#   GCP_ID_TOKEN=... sh .gitlab/ci/gcp-token.sh <out file>
# Needs GCP_WIF_PROVIDER (projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<id>)
# and GCP_SERVICE_ACCOUNT (the deploy service account email), from the variables of .gitlab-ci.yml.
set -eu
out="${1:?usage: gcp-token.sh <out file>}"
: "${GCP_ID_TOKEN:?no GitLab ID token (id_tokens: GCP_ID_TOKEN)}"
: "${GCP_WIF_PROVIDER:?GCP_WIF_PROVIDER is empty}"
: "${GCP_SERVICE_ACCOUNT:?GCP_SERVICE_ACCOUNT is empty}"
umask 077

# One JSON field of a one-line answer; the tokens have no quotes.
field() { tr -d '\n' | sed -n "s/.*\"$1\" *: *\"\([^\"]*\)\".*/\1/p"; }

federated="$(curl -sS --fail-with-body https://sts.googleapis.com/v1/token \
  --data-urlencode "grant_type=urn:ietf:params:oauth:grant-type:token-exchange" \
  --data-urlencode "audience=//iam.googleapis.com/$GCP_WIF_PROVIDER" \
  --data-urlencode "scope=https://www.googleapis.com/auth/cloud-platform" \
  --data-urlencode "requested_token_type=urn:ietf:params:oauth:token-type:access_token" \
  --data-urlencode "subject_token_type=urn:ietf:params:oauth:token-type:jwt" \
  --data-urlencode "subject_token=$GCP_ID_TOKEN" | field access_token)" \
  || { echo "gcp-token: the token exchange failed (Workload Identity provider or its condition)"; exit 1; }
[ -n "$federated" ] || { echo "gcp-token: the token exchange gave no token"; exit 1; }

curl -sS --fail-with-body \
  "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/$GCP_SERVICE_ACCOUNT:generateAccessToken" \
  -H "Authorization: Bearer $federated" -H "Content-Type: application/json" \
  -d '{"scope": ["https://www.googleapis.com/auth/cloud-platform"]}' | field accessToken > "$out" \
  || { echo "gcp-token: the service account refused the federated identity (roles/iam.workloadIdentityUser)"; exit 1; }
[ -s "$out" ] || { echo "gcp-token: no access token"; exit 1; }
echo "gcp-token: access token for $GCP_SERVICE_ACCOUNT in $out"
