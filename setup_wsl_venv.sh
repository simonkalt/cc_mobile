#!/bin/bash
# Setup script to create venv in WSL Linux filesystem and install dependencies

set -e

echo "🚀 Setting up WSL virtual environment for cc_mobile..."

# Resolve project directory (directory containing this script)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

# Create project-root venv
echo "Creating virtual environment in $VENV_DIR..."
cd "$PROJECT_DIR"
python3 -m venv "$VENV_DIR"

# Activate and upgrade pip
echo "Upgrading pip..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip setuptools wheel

# Install system dependencies for weasyprint
echo "Installing system dependencies for weasyprint..."
sudo apt update
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
    gir1.2-pango-1.0

# Install Python dependencies
echo "Installing Python dependencies..."
cd "$PROJECT_DIR"
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the server, run:"
echo "  bash start_wsl.sh"
echo ""
echo "Or manually:"
echo "  source .venv/bin/activate"
echo "  cd $PROJECT_DIR"
echo "  python -m uvicorn main:app --reload --host 0.0.0.0 --port 8675"

