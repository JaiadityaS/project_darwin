#!/usr/bin/env bash
# Repo hygiene guard. Keeps AI attribution and agent-tool files out of git.
#   guard.sh msg <file|->   check a commit message (commit-msg hook)
#   guard.sh staged         check staged paths and added lines (pre-commit hook)
#   guard.sh tree           check all tracked files (CI)
set -uo pipefail

rot13() { tr 'A-Za-z' 'N-ZA-Mn-za-m'; }
# Tool and vendor names, stored rot13-encoded so that this file does not contain them.
DENY="$(printf '%s' 'pynhqr|naguebcvp|pbcvybg|pungtcg' | rot13)"
# Co-author trailers and the robot emoji. Split so that this file does not match itself.
ATTR="co-authored""-by:|"$'\xf0\x9f\xa4\x96'

TOP_ALLOW=" .agents .floor .github .gitlab .devops docs scripts deploy infra site flows ci AGENTS.md README.md FLOOR.md LICENSE CODEOWNERS Makefile .gitignore .gitattributes .gitlab-ci.yml "
CAPS_MD_ALLOW=" README.md AGENTS.md FLOOR.md STATE.md TASKS.md DECISIONS.md PRD.md ARCHITECTURE.md CHANGELOG.md SECURITY.md CONTRIBUTING.md "

fail=0
bad() { echo "guard: $*" >&2; fail=1; }

# Reads paths on stdin. Runs in a subshell when piped, so it returns its own status.
check_paths() {
  local p top rest part base
  local -a parts
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    top="${p%%/*}"
    case "$TOP_ALLOW" in
      *" $top "*) ;;
      *) bad "top-level path not allowed: $p (add it to TOP_ALLOW in scripts/guard.sh if it is product code)" ;;
    esac
    rest="${p#"$top"}"
    rest="${rest#/}"
    parts=()
    [ -n "$rest" ] && IFS='/' read -r -a parts <<< "$rest"
    for part in "${parts[@]+"${parts[@]}"}"; do
      case "$part" in
        .gitkeep|.gitignore) ;;
        .*) bad "hidden path below the top level: $p" ;;
      esac
    done
    base="${p##*/}"
    if [[ "$base" =~ ^[A-Z_]+\.md$ ]]; then
      case "$CAPS_MD_ALLOW" in
        *" $base "*) ;;
        *) bad "unexpected all-caps markdown file: $p" ;;
      esac
    fi
    if printf '%s' "$p" | grep -qiE "$DENY"; then
      bad "denied name in path: $p"
    fi
  done
  return $fail
}

case "${1:-}" in
  msg)
    src="${2:--}"
    if [ "$src" = "-" ]; then text="$(cat)"; else text="$(cat "$src")"; fi
    body="$(printf '%s\n' "$text" | grep -v '^#' || true)"
    if printf '%s\n' "$body" | grep -qiE "$ATTR"; then
      bad "commit message has an attribution line (co-author trailer or robot emoji)"
    fi
    if printf '%s\n' "$body" | grep -qiE "$DENY"; then
      bad "commit message names an AI tool or vendor"
    fi
    ;;
  staged)
    git diff --cached --name-only --diff-filter=ACMR | check_paths || fail=1
    added="$(git diff --cached -U0 --no-color --diff-filter=ACMR | grep -E '^\+' | grep -vE '^\+\+\+ ' || true)"
    if printf '%s\n' "$added" | grep -qiE "$DENY|$ATTR"; then
      printf '%s\n' "$added" | grep -iE "$DENY|$ATTR" | head -5 >&2
      bad "staged lines contain an AI attribution or tool name"
    fi
    ;;
  tree)
    git ls-files | check_paths || fail=1
    if git grep -qIiE "$DENY" -- .; then
      git grep -nIiE "$DENY" -- . | head -10 >&2
      bad "tracked files contain an AI tool or vendor name"
    fi
    ;;
  *)
    echo "usage: guard.sh msg <file|-> | staged | tree" >&2
    exit 2
    ;;
esac
exit $fail
