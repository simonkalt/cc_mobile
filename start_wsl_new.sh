#!/bin/bash
# Start script for WSL - uses local .venv
# Run this from WSL terminal

# Navigate to project directory
cd /mnt/t/Python/cc_mobile || cd "$(dirname "$0")"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please create it first: python3 -m venv .venv"
    exit 1
fi

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✓ Activated virtual environment"
else
    echo "⚠️  No activate script found, using venv Python directly"
fi

# Determine which Python to use (prefer venv's Python)
if [ -f ".venv/bin/python3" ]; then
    PYTHON_CMD=.venv/bin/python3
    PIP_CMD=.venv/bin/pip
elif [ -f ".venv/bin/python" ]; then
    PYTHON_CMD=.venv/bin/python
    PIP_CMD=.venv/bin/pip
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
    PIP_CMD=pip
else
    PYTHON_CMD=python3
    PIP_CMD=pip3
fi

echo "Using Python: $PYTHON_CMD"
echo "Using pip: $PIP_CMD"
echo "Python version: $($PYTHON_CMD --version)"

# Check for required dependencies
echo "Checking for required dependencies..."

# Check uvicorn
if ! $PYTHON_CMD -c "import uvicorn" 2>/dev/null; then
    echo "⚠️  uvicorn not found. Installing..."
    $PIP_CMD install uvicorn
    if ! $PYTHON_CMD -c "import uvicorn" 2>/dev/null; then
        echo "❌ Failed to install uvicorn. Please install manually: $PIP_CMD install uvicorn"
        exit 1
    fi
    echo "✓ uvicorn installed successfully"
else
    echo "✓ uvicorn is available"
fi

# Check pymupdf
if ! $PYTHON_CMD -c "import fitz" 2>/dev/null; then
    echo "⚠️  pymupdf not found. Installing..."
    $PIP_CMD install pymupdf
    if ! $PYTHON_CMD -c "import fitz" 2>/dev/null; then
        echo "❌ Failed to install pymupdf. Please install manually: $PIP_CMD install pymupdf"
        exit 1
    fi
    echo "✓ pymupdf installed successfully"
else
    echo "✓ pymupdf is available"
fi

# Install/upgrade cffi first (required for cryptography)
# Only reinstall if the backend is missing
echo ""
echo "Checking cffi installation (required for cryptography)..."
if ! $PYTHON_CMD -c "import _cffi_backend" 2>/dev/null; then
    echo "⚠️  _cffi_backend not found, installing/rebuilding cffi..."
    $PIP_CMD install --upgrade --force-reinstall --no-cache-dir cffi
    # Verify it works after installation
    if ! $PYTHON_CMD -c "import _cffi_backend" 2>/dev/null; then
        echo "❌ Failed to install cffi backend. You may need system dependencies:"
        echo "   sudo apt-get install python3-dev libffi-dev build-essential"
    else
        echo "✓ cffi backend installed successfully"
    fi
else
    echo "✓ cffi backend is available"
fi

# Optionally install all requirements if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo ""
    echo "Installing/updating requirements from requirements.txt..."
    $PIP_CMD install -r requirements.txt
fi

# Start the server
echo ""
echo "Starting FastAPI server..."
$PYTHON_CMD -m uvicorn main:app --reload --host 0.0.0.0 --port 8000