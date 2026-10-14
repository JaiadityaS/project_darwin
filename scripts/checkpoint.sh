#!/usr/bin/env bash
# Saves and shares work: installs the hooks, stages everything, commits, rebases on the remote, pushes.
# Usage: bash scripts/checkpoint.sh "type(scope): summary"
set -euo pipefail
msg="${1:?usage: bash scripts/checkpoint.sh \"type(scope): summary\"}"
cd "$(git rev-parse --show-toplevel)"
bash scripts/install-hooks.sh >/dev/null

branch="$(git rev-parse --abbrev-ref HEAD)"
git add -A
if git diff --cached --quiet; then
  echo "checkpoint: nothing new to commit"
else
  git commit -q -m "$msg"
fi

if git ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
  if ! git pull --rebase --autostash -q origin "$branch"; then
    echo "checkpoint: the rebase stopped on a conflict. Fix the files, run 'git add <files>' and 'git rebase --continue', then run this script again." >&2
    exit 1
  fi
fi
git push -q -u origin "$branch"
git log -1 --format="checkpoint: pushed %h to $branch as %an <%ae>: %s"
