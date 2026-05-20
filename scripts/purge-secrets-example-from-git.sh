#!/usr/bin/env bash
# Remove .secrets.example from entire git history (all branches/tags), then
# recommit the clean template from the working tree.
#
# Why: a real REDIS_PASSWORD was committed in .secrets.example (e.g. a095420).
# After running: rotate that Redis password in Redis Cloud — history rewrite
# does not revoke leaked credentials on clones or GitHub caches.
#
# Usage (from repo root):
#   bash scripts/purge-secrets-example-from-git.sh
#
# Then sync remotes (rewrites history — coordinate with anyone else cloning):
#   git push --force-with-lease origin --all
#   git push --force-with-lease origin --tags   # if you use tags
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGET=".secrets.example"
BACKUP="$(mktemp -t secrets-example-clean.XXXXXX)"

cleanup() {
  rm -f "$BACKUP"
}
trap cleanup EXIT

if [[ ! -f "$TARGET" ]]; then
  echo "❌ Missing $ROOT/$TARGET — create the cleaned template first." >&2
  exit 1
fi

if grep -qE '^REDIS_PASSWORD=[^[:space:]#]+' "$TARGET" 2>/dev/null; then
  echo "❌ $TARGET still has a non-empty REDIS_PASSWORD. Clear it before running." >&2
  exit 1
fi

cp "$TARGET" "$BACKUP"

echo "This will:"
echo "  1. Remove $TARGET from every commit on every ref (history rewrite)"
echo "  2. Add back the clean file from: $BACKUP"
echo "  3. Create one new commit on the current branch"
echo ""
echo "⚠️  Rotate the leaked Redis password after pushing."
echo "⚠️  Everyone with a clone must re-clone or reset after you force-push."
echo ""
read -r -p "Type YES to continue: " confirm
if [[ "$confirm" != "YES" ]]; then
  echo "Aborted."
  exit 0
fi

other_dirty="$(git status --porcelain | grep -v "^.[MTADRCU?] $TARGET$" || true)"
if [[ -n "$other_dirty" ]]; then
  echo ""
  echo "❌ Commit or stash other changes first (only $TARGET may be dirty)." >&2
  git status --short
  exit 1
fi

CURRENT_BRANCH="$(git branch --show-current)"
echo ""
echo "Current branch: ${CURRENT_BRANCH:-'(detached)'}"

if command -v git-filter-repo >/dev/null 2>&1; then
  echo "Using git-filter-repo…"
  git filter-repo --path "$TARGET" --invert-paths --force
else
  echo "git-filter-repo not found; using git filter-branch (slower)."
  echo "Install for faster/safer rewrites: pip install git-filter-repo"
  export FILTER_BRANCH_SQUELCH_WARNING=1
  git filter-branch --force --index-filter \
    "git rm --cached --ignore-unmatch $TARGET" \
    --prune-empty --tag-name-filter cat -- --all
  rm -rf .git/refs/original/ 2>/dev/null || true
  git reflog expire --expire=now --all
  git gc --prune=now --aggressive
fi

cp "$BACKUP" "$TARGET"
git add "$TARGET"
git commit -m "$(cat <<'EOF'
Add cleaned .secrets.example after purging from history

Removed .secrets.example from all prior commits (accidental secret in template).
Rotate any credentials that were ever in that file.
EOF
)"

echo ""
echo "✅ History rewritten on this machine."
echo ""
echo "Next — force-push (required or GitHub still has the leak):"
echo "  git push --force-with-lease origin --all"
echo "  git push --force-with-lease origin --tags"
echo ""
echo "If GitHub blocks the push, allow secret-scanning bypass only after confirming"
echo "the password is rotated and the file no longer contains secrets."
echo ""
echo "Re-add origin if filter-repo removed it:"
echo "  git remote add origin https://github.com/simonkalt/cc_mobile.git"
