#!/bin/bash
# Start script for WSL - uses venv in Linux filesystem
# Run this from WSL terminal, not Git Bash

# Check if venv exists
if [ ! -d ~/venvs/cc_mobile ]; then
    echo "❌ Virtual environment not found!"
    echo "Run: bash setup_and_run_wsl.sh"
    exit 1
fi

# Navigate to project directory
cd /mnt/t/Python/cc_mobile

# Activate virtual environment from WSL Linux filesystem
source ~/venvs/cc_mobile/bin/activate

# Start the server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

