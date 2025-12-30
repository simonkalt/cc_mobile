# Fix WSL Terminal Errors on Startup

## Problem
Your WSL terminal is trying to activate a virtual environment that:
1. Uses Windows path format (`T:/fastapi/...`) instead of WSL format (`/mnt/t/fastapi/...`)
2. Points to a location that doesn't exist
3. Uses `Scripts/activate` (Windows) instead of `bin/activate` (Linux)

## Errors You're Seeing

```
source T:/fastapi/code/myproj/.venv/Scripts/activate
-bash: T:/fastapi/code/myproj/.venv/Scripts/activate: No such file or directory
```

The "sudo" message is normal - it's just Ubuntu's welcome message.

## Solutions

### Option 1: Remove the Auto-Activation (Recommended)

If you don't need to auto-activate that venv, remove the command from wherever it's being auto-run:

1. **Check if it's in your shell config:**
   ```bash
   grep -r "T:/fastapi" ~/.bashrc ~/.bash_profile ~/.profile ~/.bash_aliases 2>/dev/null
   ```

2. **If found, edit the file and remove or comment out the line:**
   ```bash
   # Comment it out:
   # source T:/fastapi/code/myproj/.venv/Scripts/activate
   ```

3. **Restart your terminal**

### Option 2: Fix the Path (If You Need That Venv)

If the virtual environment exists but at a different location:

1. **Find the correct path:**
   ```bash
   # Search for activate scripts
   find /mnt/t -name "activate" -path "*/.venv/bin/activate" 2>/dev/null
   ```

2. **Use the correct WSL path format:**
   ```bash
   # Windows: T:/fastapi/code/myproj/.venv/Scripts/activate
   # WSL:     /mnt/t/fastapi/code/myproj/.venv/bin/activate
   
   source /mnt/t/fastapi/code/myproj/.venv/bin/activate
   ```

3. **Add to your `.bashrc` if you want it to auto-activate:**
   ```bash
   # Add this line to ~/.bashrc (only if the venv exists!)
   if [ -f "/mnt/t/fastapi/code/myproj/.venv/bin/activate" ]; then
       source /mnt/t/fastapi/code/myproj/.venv/bin/activate
   fi
   ```

### Option 3: Create a Venv in Your Current Project

If you want to use a virtual environment for this project:

```bash
# Navigate to your project
cd /mnt/t/Python/cc_mobile

# Create a virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

Then add to `~/.bashrc`:
```bash
# Auto-activate venv when in this project directory
if [ -f "/mnt/t/Python/cc_mobile/.venv/bin/activate" ]; then
    cd() {
        builtin cd "$@"
        if [[ "$PWD" == "/mnt/t/Python/cc_mobile"* ]] && [ -f ".venv/bin/activate" ]; then
            source .venv/bin/activate
        fi
    }
fi
```

## Quick Fix (Remove the Error)

To immediately stop the error, check where it's being called from:

```bash
# Check all config files
cat ~/.bashrc | grep -i "fastapi\|venv\|activate"
cat ~/.bash_profile 2>/dev/null | grep -i "fastapi\|venv\|activate"
cat ~/.profile | grep -i "fastapi\|venv\|activate"
cat ~/.bash_aliases 2>/dev/null | grep -i "fastapi\|venv\|activate"
```

If you find it, comment it out or remove it.

## Verify Fix

After making changes:
1. Close and reopen your WSL terminal
2. You should no longer see the error
3. The "sudo" message is normal and can be ignored

