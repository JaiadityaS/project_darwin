#!/bin/sh
# Gate checks that need git: the tools image tag, the Leave-Behind Notices (F6), the policy
# ratchet (F1.2) and, on merge requests, the agent path allowlist (F4.2, §10.1, D-010).
# The check job runs it from the repository root, with the full history.
set -eu

# 1. The tools image comes from the committed recipe: its tag is the recipe's hash.
want="$(sha256sum .gitlab/ci/tools.Dockerfile | cut -c 1-12)"
if [ "$want" != "$TOOLS_TAG" ]; then
  echo "check.sh: TOOLS_TAG is $TOOLS_TAG, but .gitlab/ci/tools.Dockerfile hashes to $want. Set TOOLS_TAG in .gitlab-ci.yml." >&2
  exit 1
fi
echo "tools image tag $TOOLS_TAG matches its recipe"

# 2. Every notice is complete.
set -- .floor/notices/[0-9]*.md
if [ -e "$1" ]; then floor notice "$@"; else echo "no notices"; fi

# 3. A looser policy needs a notice that is already merged on the base, and the GitLab approvals of
#    its MR must show a human code owner and no other account (F6.1). The approvals of a public
#    project need no token.
zero=0000000000000000000000000000000000000000
base=""
if [ -n "${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:-}" ]; then
  base="origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME"
  git fetch -q origin "+refs/heads/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME:refs/remotes/$base"
elif [ "${CI_COMMIT_BEFORE_SHA:-$zero}" != "$zero" ] && git cat-file -e "$CI_COMMIT_BEFORE_SHA:.floor/policy.yml" 2> /dev/null; then
  base="$CI_COMMIT_BEFORE_SHA"
fi
if [ -n "$base" ]; then
  floor ratchet --base "$base" --approvals "$CI_API_V4_URL/projects/$CI_PROJECT_ID" --default-branch "$CI_DEFAULT_BRANCH"
else
  echo "no earlier policy to compare with"
fi

# 4. Merge requests: deny by default. The pipeline user and the MR author (from the API) must
#    both be in FLOOR_HUMANS. Otherwise the MR counts as an agent MR, and an agent may change
#    only the allowlist paths. Humans need code-owner review.
if [ -n "${CI_MERGE_REQUEST_IID:-}" ]; then
  floor paths --actor auto --base "$base"
fi
