#!/bin/bash

# Resolve project directory (directory containing this script)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found!"
    echo "Run: bash setup_and_run.sh"
    exit 1
fi

# Navigate to project directory
cd "$PROJECT_DIR"

# shellcheck source=scripts/env-files.sh
source "$PROJECT_DIR/scripts/env-files.sh"
require_env_files "$PROJECT_DIR" || exit 1

# Activate project-root virtual environment
source "$VENV_DIR/bin/activate"

# Start the server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8675

