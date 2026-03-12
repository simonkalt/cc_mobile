#!/bin/bash
# Install system dependencies for weasyprint in WSL

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

echo "✓ System dependencies installed"
echo ""
echo "You may need to restart your server for weasyprint to work properly."

