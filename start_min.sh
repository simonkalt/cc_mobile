#!/bin/bash
# Minimal start script for WSL - no library checks, just start the app
# Run this from WSL terminal

# Navigate to project directory
cd /mnt/t/Python/cc_mobile || cd "$(dirname "$0")"

# Activate virtual environment from WSL Linux filesystem
# Try common venv locations
if [ -d ~/venvs/cc_mobile ]; then
    source ~/venvs/cc_mobile/bin/activate
elif [ -d venv ]; then
    source venv/bin/activate
elif [ -d .venv ]; then
    source .venv/bin/activate
else
    echo "⚠️  No virtual environment found. Starting without venv..."
fi

# Start the server - try app.main:app first (refactored), fallback to main:app (legacy)
# Add timeout-graceful-shutdown to prevent hanging on Ctrl+C
# Reduced timeout to 2 seconds for faster shutdown
if python -c "from app.main import app" 2>/dev/null; then
    echo "Starting FastAPI server (refactored structure)..."
    echo "Press Ctrl+C to stop the server (press twice to force exit)"
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 2
else
    echo "Starting FastAPI server (legacy structure)..."
    echo "Press Ctrl+C to stop the server (press twice to force exit)"
    python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 2
fi

