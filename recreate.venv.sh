#!/usr/bin/env bash
# Force-recreate a broken or stale .venv (safe to run anytime).
set -e
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

command -v deactivate >/dev/null 2>&1 && deactivate 2>/dev/null || true
rm -rf .venv

# shellcheck source=scripts/ensure_venv.sh
source "$PROJECT_DIR/scripts/ensure_venv.sh"
ensure_project_venv "$PROJECT_DIR"