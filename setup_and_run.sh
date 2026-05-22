#!/bin/bash
# Complete setup and run script for WSL
# Run this from WSL terminal: bash setup_and_run_wsl.sh
set -e
echo "🚀 Setting up WSL environment and starting server..."
# Resolve project directory (directory containing this script)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# shellcheck source=scripts/env-files.sh
source "$PROJECT_DIR/scripts/env-files.sh"
require_env_files "$PROJECT_DIR" || exit 1

# shellcheck source=scripts/ensure_venv.sh
source "$PROJECT_DIR/scripts/ensure_venv.sh"
ensure_project_venv "$PROJECT_DIR" || exit 1

VENV_DIR="$PROJECT_DIR/.venv"
source "$VENV_DIR/bin/activate"
# Step 6: Start server
echo ""
echo "🚀 Starting FastAPI server..."
echo "   Access at: http://localhost:8675"
echo "   Docs at: http://localhost:8675/docs"
echo ""
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8675