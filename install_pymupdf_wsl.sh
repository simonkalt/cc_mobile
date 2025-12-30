#!/bin/bash
# Install pymupdf in WSL Python environment
# Run this script from WSL terminal (not Git Bash)

echo "Installing pymupdf in WSL Python environment..."

# Navigate to project directory
cd /mnt/t/Python/cc_mobile || cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please create it first: python3 -m venv .venv"
    exit 1
fi

# Activate venv (if bash activate exists)
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✓ Activated virtual environment"
else
    echo "⚠️  No activate script found, using venv Python directly"
fi

# Install pymupdf using the venv's Python
if [ -f ".venv/bin/python3" ]; then
    echo "Installing pymupdf using venv Python..."
    .venv/bin/python3 -m pip install pymupdf
elif [ -f ".venv/bin/python" ]; then
    echo "Installing pymupdf using venv Python..."
    .venv/bin/python -m pip install pymupdf
else
    # Fallback: use system Python but install to venv
    echo "Installing pymupdf to venv site-packages..."
    python3 -m pip install --target .venv/lib/python3.12/site-packages --no-user pymupdf
fi

# Verify installation
echo ""
echo "Verifying installation..."
python3 -c "import sys; sys.path.insert(0, '.venv/lib/python3.12/site-packages'); import fitz; print('✓ pymupdf installed successfully! Version:', fitz.version[0])" 2>/dev/null || \
python3 -c "import fitz; print('✓ pymupdf installed successfully! Version:', fitz.version[0])" 2>/dev/null || \
echo "⚠️  Could not verify installation. Please check manually."

echo ""
echo "Done! Restart your FastAPI server to use pymupdf."

