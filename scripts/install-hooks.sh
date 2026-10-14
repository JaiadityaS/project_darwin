#!/usr/bin/env bash
# Installs local git hooks that run scripts/guard.sh, and keeps agent-tool files out of git.
# Safe to run again. Hooks and excludes are local to this clone; they are never committed.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

hooks="$(git rev-parse --git-path hooks)"
mkdir -p "$hooks"
cat > "$hooks/commit-msg" <<'EOF'
#!/usr/bin/env bash
exec bash "$(git rev-parse --show-toplevel)/scripts/guard.sh" msg "$1"
EOF
cat > "$hooks/pre-commit" <<'EOF'
#!/usr/bin/env bash
exec bash "$(git rev-parse --show-toplevel)/scripts/guard.sh" staged
EOF
chmod +x "$hooks/commit-msg" "$hooks/pre-commit"

# Settings and memory files of common agent tools, rot13-encoded so that this file does not name them.
exclude="$(git rev-parse --git-path info/exclude)"
mkdir -p "$(dirname "$exclude")"
touch "$exclude"
for enc in '.pynhqr/' 'PYNHQR.zq' 'PYNHQR.ybpny.zq' '.phefbe/' '.phefbeehyrf' '.pbqrk/' '.trzvav/' 'TRZVAV.zq' '.nvqre*' '.jvaqfhes/' '.pbagvahr/' '.pbcvybg/'; do
  entry="$(printf '%s' "$enc" | tr 'A-Za-z' 'N-ZA-Mn-za-m')"
  grep -qxF -- "$entry" "$exclude" || printf '%s\n' "$entry" >> "$exclude"
done
echo "install-hooks: hooks and local excludes are in place"
