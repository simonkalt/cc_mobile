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

# Verify redis is installed
echo "Checking for redis..."
if ! python -c "import redis" 2>/dev/null; then
    echo "⚠️  Redis not found. Installing..."
    pip install redis
    if ! python -c "import redis" 2>/dev/null; then
        echo "❌ Failed to install redis. Please install manually: pip install redis"
        exit 1
    fi
    echo "✓ Redis installed successfully"
else
    echo "✓ Redis is available"
fi

# Start the server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

