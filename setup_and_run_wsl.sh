#!/bin/bash
# Complete setup and run script for WSL
# Run this from WSL terminal: bash setup_and_run_wsl.sh
set -e
echo "🚀 Setting up WSL environment and starting server..."
# Resolve project directory (directory containing this script)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"
VENV_DIR="$PROJECT_DIR/.venv"
# Step 1: Create project-root venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
# Step 2: Activate venv
source "$VENV_DIR/bin/activate"
# Step 3: Map python -> python3
if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "🔗 Mapping python -> python3..."
    ln -s "$VENV_DIR/bin/python3" "$VENV_DIR/bin/python"
    echo "✓ python mapped to python3"
else
    echo "✓ python already mapped"
fi
# Step 4: Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip setuptools wheel --quiet
# Step 5: Install Python dependencies
echo "📦 Installing Python dependencies..."
if ! pip list | grep -q fastapi; then
    pip install -r requirements.txt
    echo "✓ Python dependencies installed"
else
    echo "✓ Python dependencies already installed"
fi
# Step 6: Start server
echo ""
echo "🚀 Starting FastAPI server..."
echo "   Access at: http://localhost:8675"
echo "   Docs at: http://localhost:8675/docs"
echo ""
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8675