#!/bin/bash
# Complete setup and run script for WSL
# Run this from WSL terminal: bash setup_and_run_wsl.sh

set -e

echo "🚀 Setting up WSL environment and starting server..."

# Navigate to project
cd /mnt/t/Python/cc_mobile

# Step 1: Create venv in Linux filesystem if it doesn't exist
if [ ! -d ~/venvs/cc_mobile ]; then
    echo "📦 Creating virtual environment..."
    mkdir -p ~/venvs
    python3 -m venv ~/venvs/cc_mobile
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Step 2: Activate venv
source ~/venvs/cc_mobile/bin/activate

# Step 3: Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip setuptools wheel --quiet

# Step 4: Check if system libraries are installed
echo "🔍 Checking system dependencies..."
if ! ldconfig -p 2>/dev/null | grep -q libgobject-2.0; then
    echo "📥 Installing system dependencies for weasyprint..."
    sudo apt update -qq
    sudo apt install -y \
        libgobject-2.0-0 \
        libglib2.0-0 \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        libffi-dev \
        shared-mime-info \
        libxml2-dev \
        libxslt1-dev \
        libjpeg-dev \
        zlib1g-dev \
        python3-dev \
        python3-cffi \
        libgirepository-1.0-1 \
        gir1.2-pango-1.0 > /dev/null 2>&1
    echo "✓ System dependencies installed"
else
    echo "✓ System dependencies already installed"
fi

# Step 5: Install Python dependencies
echo "📦 Installing Python dependencies..."
if ! pip list | grep -q fastapi; then
    pip install -r requirements.txt
    echo "✓ Python dependencies installed"
else
    echo "✓ Python dependencies already installed"
fi

# Step 6: Verify weasyprint works
echo "🧪 Testing weasyprint..."
if python -c "from weasyprint import HTML; print('✓ WeasyPrint works!')" 2>/dev/null; then
    echo "✓ WeasyPrint is working!"
else
    echo "⚠️  WeasyPrint test failed, but continuing..."
fi

# Step 7: Start server
echo ""
echo "🚀 Starting FastAPI server..."
echo "   Access at: http://localhost:8000"
echo "   Docs at: http://localhost:8000/docs"
echo ""
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

