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

# Product paths (D-002, D-017). Everything else in this repo is dev-only.
PRODUCT=(.floor .gitlab .gitlab-ci.yml deploy infra README.md)
# Paths that the repair agent may change on GitLab (.floor/floor/paths.py AGENT_ALLOWED).
# A sync never overwrites or deletes a file there that an agent changed after the last sync. A file that only
# a sync wrote follows this repo's HEAD (D-034).
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
# The Rieux README is the front page (T-90, D-017). whisper.cpp's README moves once, to the same folder,
# so its relative links still work.
if [ ! -e "$WORK/README.whisper.cpp.md" ] && [ -e "$WORK/README.md" ]; then
  G mv README.md README.whisper.cpp.md
fi
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
# An agent changed a file when its GitLab blob differs from the blob of the dev commit of the last sync.
last="$(G log -1 --format=%s --grep='^chore(floor): sync Floor files from dev ' | sed -n 's/^chore(floor): sync Floor files from dev //p')"
git cat-file -e "${last:-none}^{commit}" 2>/dev/null || last=""
for p in "${AGENT_OWNED[@]}"; do
  [ -e "$keep/$p" ] || continue
  while IFS= read -r -d '' f; do
    rel="${f#"$keep/"}"
    if [ -n "$last" ] && [ "$(git rev-parse -q --verify "$last:$rel" || true)" = "$(G rev-parse -q --verify "HEAD:$rel" || true)" ]; then
      continue
    fi
    mkdir -p "$WORK/$(dirname "$rel")" && cp -a "$f" "$WORK/$rel"
  done < <(find "$keep/$p" -type f -print0)
done
G add -A
if G diff --cached --quiet; then
  say "no Floor changes since the last sync"
else
  commit "chore(floor): sync Floor files from dev $DEV_SHA"
fi

# 4. Report, then push only on request.
ahead="$(G rev-list --count "origin/$BRANCH..HEAD")"
ours="$(G rev-list --count "origin/$BRANCH..HEAD" "^$UPSTREAM_COMMIT")"
say "work/gitlab is $ahead commit(s) ahead of GitLab $BRANCH. Floor commits ($ours):"
G log --oneline "origin/$BRANCH..HEAD" "^$UPSTREAM_COMMIT" | sed 's/^/  /'
[ "$ahead" -gt "$ours" ] && say "  plus $((ahead - ours)) upstream whisper.cpp commit(s) from the import"
if [ "$ahead" -eq 0 ]; then
  say "nothing to push"
elif [ "$PUSH" -eq 1 ]; then
  G push -u origin "HEAD:$BRANCH"
  say "pushed to $GITLAB_URL ($BRANCH) as $(git config user.name)"
else
  say "dry run: nothing pushed. Check work/gitlab, then run the same command with --push"
fi
