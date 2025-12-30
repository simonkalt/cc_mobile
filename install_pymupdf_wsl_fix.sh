#!/bin/bash
# Install pymupdf properly in WSL Python environment
# This script ensures it's installed in the correct Python that the server uses

echo "Installing pymupdf in WSL Python environment..."
echo ""

# Navigate to project directory
cd /mnt/t/Python/cc_mobile || cd "$(dirname "$0")"

# Check what Python the venv uses
VENV_PYTHON=$(cat .venv/pyvenv.cfg | grep "^executable" | cut -d'=' -f2 | tr -d ' ')
echo "Venv Python: $VENV_PYTHON"

# Check if that Python exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "⚠️  Venv Python not found at $VENV_PYTHON"
    echo "Trying to find Python 3.12..."
    VENV_PYTHON=$(which python3.12 2>/dev/null || which python3 2>/dev/null)
    echo "Using: $VENV_PYTHON"
fi

# Install using the correct Python
if [ -f "$VENV_PYTHON" ]; then
    echo "Installing pymupdf using: $VENV_PYTHON"
    "$VENV_PYTHON" -m pip install --upgrade pymupdf
    
    echo ""
    echo "Verifying installation..."
    "$VENV_PYTHON" -c "import fitz; print('✓ pymupdf imported successfully!'); print('Version:', fitz.version[0] if hasattr(fitz, 'version') else 'unknown')" 2>&1
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ pymupdf is installed and working!"
        echo ""
        echo "Please restart your FastAPI server for the changes to take effect."
    else
        echo ""
        echo "❌ Installation verification failed."
        echo "The library files are present but Python cannot import them."
        echo "This might be a compatibility issue. Try:"
        echo "  1. Make sure you're using WSL Python (not Windows Python)"
        echo "  2. Check that the venv is activated when running the server"
        echo "  3. Try: pip uninstall pymupdf && pip install pymupdf"
    fi
else
    echo "❌ Could not find Python executable"
    echo "Please install pymupdf manually:"
    echo "  source .venv/bin/activate"
    echo "  pip install pymupdf"
fi

