#!/bin/bash
# Check if redis is installed in the correct venv

echo "Checking Redis installation..."
echo ""

# Check if venv exists
if [ ! -d ~/venvs/cc_mobile ]; then
    echo "❌ Virtual environment not found at ~/venvs/cc_mobile"
    exit 1
fi

echo "✓ Virtual environment found at ~/venvs/cc_mobile"
echo ""

# Activate venv
source ~/venvs/cc_mobile/bin/activate

echo "Python executable: $(which python)"
echo "Python version: $(python --version)"
echo ""

# Check if redis is installed
echo "Checking for redis package..."
if python -c "import redis; print(f'✓ redis version: {redis.__version__}')" 2>/dev/null; then
    echo "✓ Redis is installed and importable"
    echo ""
    echo "Package location:"
    python -c "import redis; print(f'  {redis.__file__}')"
else
    echo "❌ Redis is NOT installed in this venv"
    echo ""
    echo "Installing redis..."
    pip install redis
    echo ""
    echo "Verifying installation..."
    if python -c "import redis; print(f'✓ redis version: {redis.__version__}')" 2>/dev/null; then
        echo "✓ Redis installed successfully!"
    else
        echo "❌ Installation failed"
        exit 1
    fi
fi

echo ""
echo "IMPORTANT: Restart your server after installing redis!"

