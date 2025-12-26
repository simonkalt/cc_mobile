# WeasyPrint in WSL - Complete Fix

## The Problem

WeasyPrint **CAN work in WSL**, but you need to:
1. ✅ Create the virtual environment in WSL's Linux filesystem (not Windows mount)
2. ✅ Install system libraries in WSL
3. ✅ Run the server from WSL

## Why It Wasn't Working

- Creating venv on `/mnt/t/` (Windows filesystem) causes permission errors
- WeasyPrint needs Linux system libraries, not Windows DLLs
- Running from Windows Python won't find Linux libraries

## Solution

### Step 1: Create venv in WSL Linux filesystem

```bash
# In WSL terminal
mkdir -p ~/venvs
cd ~/venvs
python3 -m venv cc_mobile
```

### Step 2: Install system dependencies

```bash
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
```

### Step 3: Install Python dependencies

```bash
source ~/venvs/cc_mobile/bin/activate
cd /mnt/t/Python/cc_mobile
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Step 4: Use the WSL start script

```bash
cd /mnt/t/Python/cc_mobile
bash start_wsl.sh
```

## Quick Setup (Automated)

Run the setup script:

```bash
cd /mnt/t/Python/cc_mobile
bash setup_wsl_venv.sh
```

This will:
- ✅ Create venv in `~/venvs/cc_mobile` (Linux filesystem)
- ✅ Install all system dependencies
- ✅ Install all Python packages
- ✅ Set everything up correctly

## Verify WeasyPrint Works

After setup, test:

```bash
source ~/venvs/cc_mobile/bin/activate
python -c "from weasyprint import HTML; print('✓ WeasyPrint works!')"
```

If you see `✓ WeasyPrint works!`, you're all set!

## Important Notes

- **Always run from WSL**, not Windows
- **Use `start_wsl.sh`** instead of `start.sh` when in WSL
- **Venv location**: `~/venvs/cc_mobile` (Linux filesystem)
- **Project location**: `/mnt/t/Python/cc_mobile` (Windows mount is fine for code)

## Troubleshooting

### "Operation not permitted" errors
- Don't create venv on `/mnt/` drives
- Use Linux filesystem: `~/venvs/` or `/tmp/`

### "libgobject-2.0-0 not found"
- Make sure you installed all system dependencies
- Restart WSL after installing: `wsl --shutdown` then reopen

### Server runs but WeasyPrint still fails
- Make sure you're using the WSL venv: `source ~/venvs/cc_mobile/bin/activate`
- Verify libraries: `ldconfig -p | grep gobject`

