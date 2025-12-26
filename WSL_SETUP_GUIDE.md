# WSL Environment Setup Guide

Complete guide to set up your WSL environment for the cc_mobile FastAPI application.

## Quick Setup (Automated)

Run the setup script:

```bash
cd /mnt/t/Python/cc_mobile
bash setup_wsl.sh
```

This will:
- ✅ Install Python 3 and pip (if not already installed)
- ✅ Install system dependencies for weasyprint (PDF generation)
- ✅ Create a virtual environment
- ✅ Install all Python dependencies from `requirements.txt`

## Manual Setup Steps

If you prefer to do it manually:

### 1. Install Python and pip

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

### 2. Install System Dependencies

Some packages (like `weasyprint`) need system libraries:

```bash
sudo apt install -y \
    python3-dev \
    python3-cffi \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev
```

### 3. Create Virtual Environment

```bash
cd /mnt/t/Python/cc_mobile
python3 -m venv .venv
```

### 4. Activate Virtual Environment

```bash
source .venv/bin/activate
```

You should see `(.venv)` in your prompt.

### 5. Upgrade pip

```bash
pip install --upgrade pip setuptools wheel
```

### 6. Install Python Dependencies

```bash
pip install -r requirements.txt
```

## Starting the Server

### Option 1: Using the start script

```bash
bash start.sh
```

The updated `start.sh` will automatically:
- Activate the virtual environment
- Start the uvicorn server

### Option 2: Manual start

```bash
# Activate venv
source .venv/bin/activate

# Start server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Direct command (if venv is activated)

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Auto-Activate Virtual Environment (Optional)

To automatically activate the venv when you `cd` into the project directory, add this to your `~/.bashrc`:

```bash
# Auto-activate venv for cc_mobile project
cd() {
    builtin cd "$@"
    if [[ "$PWD" == "/mnt/t/Python/cc_mobile" ]] && [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    fi
}
```

Then reload your shell:
```bash
source ~/.bashrc
```

## Verify Installation

Check that everything is installed:

```bash
# Activate venv
source .venv/bin/activate

# Check Python version
python --version

# Check installed packages
pip list

# Verify uvicorn
uvicorn --version

# Test the server starts (Ctrl+C to stop)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Troubleshooting

### "python: command not found"
- Use `python3` instead of `python`
- Or create an alias: `alias python=python3`

### "pip: command not found"
- Install pip: `sudo apt install python3-pip`
- Or use: `python3 -m pip`

### "weasyprint" installation fails
- Make sure you installed all system dependencies (step 2 above)
- On WSL, you might need: `sudo apt install libgobject-2.0-0`

### Permission errors
- Don't use `chmod` on Windows filesystems (`/mnt/t/`)
- Just run scripts with `bash script.sh`

### Virtual environment not activating
- Make sure you're in the project directory
- Check that `.venv` directory exists
- Use full path: `source /mnt/t/Python/cc_mobile/.venv/bin/activate`

## Required Dependencies

The application requires:
- **Python 3.9+** (you have 3.12.3 ✓)
- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **MongoDB** - Database (via pymongo)
- **boto3** - AWS S3 access
- **weasyprint** - PDF generation
- And many more (see `requirements.txt`)

## Next Steps

After setup:
1. ✅ Configure `.env` file with your MongoDB URI and API keys
2. ✅ Test the server: `bash start.sh`
3. ✅ Visit `http://localhost:8000/docs` for API documentation
4. ✅ Start developing!

