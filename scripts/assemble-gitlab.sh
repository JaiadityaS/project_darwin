#!/usr/bin/env bash
# Builds the GitLab submission project from this repo (task T-02, DECISIONS D-001, D-002, D-012).
#
#   bash scripts/assemble-gitlab.sh           dry run: build the commits in work/gitlab, push nothing
#   bash scripts/assemble-gitlab.sh --push    build the commits, then push them to GitLab main
#
# What it does:
#   1. Clones the GitLab project into work/gitlab (or updates the clone).
#   2. First run only: merges whisper.cpp at the pinned commit (.floor/upstream.env), with its full history.
#   3. Copies the product files of this repo's HEAD commit on top. Dev-only files never leave this repo.
#   4. Commits the result. Pushes only with --push.
#
# The push uses your own git identity and your own GitLab sign-in (Git Credential Manager opens the browser).
# The script never reads, stores or asks for a token.
set -euo pipefail

GITLAB_URL="${GITLAB_URL:-https://gitlab.com/gitlab-ai-hackathon/transcend-october-2026/43085222/showcase.git}"
BRANCH="${BRANCH:-main}"
PUSH=0
case "${1:-}" in
  --push) PUSH=1 ;;
  "") ;;
  *) echo "usage: bash scripts/assemble-gitlab.sh [--push]" >&2; exit 2 ;;
esac

# Product paths (D-002). Everything else in this repo is dev-only.
PRODUCT=(.floor .gitlab .gitlab-ci.yml deploy infra)
# Paths that the repair agent may change on GitLab (.floor/floor/paths.py AGENT_ALLOWED).
# A sync adds new files there, but never overwrites or deletes the agent's files.
AGENT_OWNED=(.floor/overrides deploy)

die() { echo "assemble: $*" >&2; exit 1; }
say() { echo "assemble: $*"; }

DEV="$(git rev-parse --show-toplevel)"
cd "$DEV"
env_url="${UPSTREAM_URL:-}" env_commit="${UPSTREAM_COMMIT:-}"
# shellcheck source=/dev/null
. .floor/upstream.env
UPSTREAM_URL="${env_url:-$UPSTREAM_URL}" UPSTREAM_COMMIT="${env_commit:-$UPSTREAM_COMMIT}"
[ -n "${UPSTREAM_URL:-}" ] && [ -n "${UPSTREAM_COMMIT:-}" ] || die ".floor/upstream.env must set UPSTREAM_URL and UPSTREAM_COMMIT"

[ -n "$(git config user.name)" ] && [ -n "$(git config user.email)" ] || die "set your git user.name and user.email first"
[ -z "$(git status --porcelain -- "${PRODUCT[@]}")" ] || die "commit the product files first (git status shows changes below ${PRODUCT[*]})"
bash scripts/guard.sh tree || die "the hygiene guard failed on this repo"

DEV_SHA="$(git rev-parse --short HEAD)"
WORK="$DEV/work/gitlab"
present=()
for p in "${PRODUCT[@]}"; do
  [ -n "$(git ls-tree --name-only HEAD -- "$p")" ] && present+=("$p")
done

# 1. The GitLab clone. Our own scratch clone: a reset only drops commits that a run made and did not push.
if [ -d "$WORK/.git" ]; then
  git -C "$WORK" remote set-url origin "$GITLAB_URL"
  git -C "$WORK" fetch -q origin "$BRANCH"
  git -C "$WORK" checkout -q -B "$BRANCH" "origin/$BRANCH"
  git -C "$WORK" reset -q --hard "origin/$BRANCH"
  git -C "$WORK" clean -q -fdx
else
  mkdir -p "$(dirname "$WORK")"
  git -c core.autocrlf=false clone -q --branch "$BRANCH" "$GITLAB_URL" "$WORK"
fi
git -C "$WORK" config core.autocrlf false
G() { git -C "$WORK" "$@"; }
commit() {
  printf '%s\n' "$1" | bash "$DEV/scripts/guard.sh" msg - || die "commit message failed the guard"
  G commit -q -m "$1"
}

# 2. Import whisper.cpp once, with its history, so the GitLab log shows where upstream ends and Floor starts.
if G cat-file -e "$UPSTREAM_COMMIT^{commit}" 2>/dev/null && G merge-base --is-ancestor "$UPSTREAM_COMMIT" HEAD; then
  say "whisper.cpp ${UPSTREAM_COMMIT:0:8} is already imported"
else
  say "fetching whisper.cpp ${UPSTREAM_COMMIT:0:8} with history (about 50 MB, once)"
  G fetch -q --no-tags "$UPSTREAM_URL" "$UPSTREAM_COMMIT"
  # The project starts with a template README. whisper.cpp's own files win every conflict.
  G merge -q --no-commit --allow-unrelated-histories "$UPSTREAM_COMMIT" >/dev/null 2>&1 || true
  G diff --name-only --diff-filter=U -z | xargs -0 -r git -C "$WORK" checkout "$UPSTREAM_COMMIT" --
  [ -z "$(G diff --name-only --diff-filter=U)" ] || die "unexpected conflicts in the import merge"
  commit "chore(import): whisper.cpp at ${UPSTREAM_COMMIT:0:12} (MIT)

Source: $UPSTREAM_URL
Commit: $UPSTREAM_COMMIT
Upstream history is kept. Every later commit is Floor work."
fi

# 3. Overlay the product files from HEAD (committed content only, no local files).
keep="$(mktemp -d)"
trap 'rm -rf "$keep"' EXIT
for p in "${AGENT_OWNED[@]}"; do
  [ -e "$WORK/$p" ] && mkdir -p "$keep/$(dirname "$p")" && cp -a "$WORK/$p" "$keep/$p"
done
for p in "${PRODUCT[@]}"; do
  G rm -r -q --ignore-unmatch -- "$p" >/dev/null
  rm -rf "${WORK:?}/$p"
done
[ ${#present[@]} -eq 0 ] || git -c core.autocrlf=false archive --format=tar HEAD -- "${present[@]}" | tar -x -C "$WORK"
for p in "${AGENT_OWNED[@]}"; do
  [ -e "$keep/$p" ] && mkdir -p "$WORK/$p" && cp -a "$keep/$p/." "$WORK/$p/"
done
G add -A
if G diff --cached --quiet; then
  say "no Floor changes since the last sync"
else
  commit "chore(floor): sync Floor files from dev $DEV_SHA"
fi

# 4. Report, then push only on request.
ahead="$(G rev-list --count "origin/$BRANCH..HEAD")"
say "work/gitlab is $ahead commit(s) ahead of GitLab $BRANCH:"
G log --oneline --max-count=5 "origin/$BRANCH..HEAD" | sed 's/^/  /'
[ "$ahead" -gt 5 ] && say "  (the import brings the upstream history; only the commits above are new work)"
if [ "$ahead" -eq 0 ]; then
  say "nothing to push"
elif [ "$PUSH" -eq 1 ]; then
  G push -u origin "HEAD:$BRANCH"
  say "pushed to $GITLAB_URL ($BRANCH) as $(git config user.name)"
else
  say "dry run: nothing pushed. Check work/gitlab, then run: bash scripts/assemble-gitlab.sh --push"
fi
