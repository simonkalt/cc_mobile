#!/bin/bash
# Start script for WSL - uses project-root venv
# Run this from WSL terminal, not Git Bash

# Resolve project directory (directory containing this script)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

# Check if venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "❌ Virtual environment not found!"
    echo "Run: bash setup_and_run_wsl.sh"
    exit 1
fi

# Navigate to project directory
cd "$PROJECT_DIR"

# Activate project-root virtual environment
source "$VENV_DIR/bin/activate"

# Start the server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8675

