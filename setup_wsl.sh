#!/bin/bash
# WSL Environment Setup Script for cc_mobile FastAPI Application

# Don't exit on error - we'll handle errors manually
set +e

echo "🚀 Setting up WSL environment for cc_mobile..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Python 3 is installed
echo -e "${YELLOW}Checking Python installation...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Python 3 is not installed. Installing...${NC}"
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv
else
    echo -e "${GREEN}✓ Python 3 is installed: $(python3 --version)${NC}"
fi

# Note: Modern Ubuntu uses externally-managed Python (PEP 668)
# We'll use venv's pip instead of system pip
echo -e "${YELLOW}Note: Using virtual environment's pip (system Python is externally managed)${NC}"

# Install system dependencies for weasyprint (PDF generation)
echo -e "${YELLOW}Installing system dependencies for weasyprint...${NC}"
sudo apt update
sudo apt install -y \
    python3-dev \
    python3-cffi \
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
    libgirepository-1.0-1 \
    gir1.2-pango-1.0

# Navigate to project directory
cd /mnt/t/Python/cc_mobile

# Create virtual environment if it doesn't exist
echo -e "${YELLOW}Setting up virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    echo -e "${GREEN}Creating virtual environment...${NC}"
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create venv. Installing python3-venv...${NC}"
        sudo apt update
        sudo apt install -y python3-venv python3-full
        python3 -m venv .venv
    fi
else
    echo -e "${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate

# Verify venv pip is available
if ! .venv/bin/pip --version &> /dev/null; then
    echo -e "${RED}Error: venv pip not available. Trying to fix...${NC}"
    python3 -m ensurepip --upgrade || python3 -m venv --clear .venv
fi

# Upgrade pip using venv's pip
echo -e "${YELLOW}Upgrading pip...${NC}"
.venv/bin/pip install --upgrade pip setuptools wheel

# Install Python dependencies using venv's pip
echo -e "${YELLOW}Installing Python dependencies from requirements.txt...${NC}"
.venv/bin/pip install -r requirements.txt

echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${GREEN}To activate the virtual environment in the future, run:${NC}"
echo "  source .venv/bin/activate"
echo ""
echo -e "${GREEN}To start the server, run:${NC}"
echo "  python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo -e "${GREEN}Or use the start script:${NC}"
echo "  bash start.sh"

