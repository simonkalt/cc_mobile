#!/bin/bash
# Run script that works from both Windows Git Bash and WSL
# Detects environment and runs appropriately

# Check if we're in WSL
if grep -qEi "(Microsoft|WSL)" /proc/version &> /dev/null || [ -f /proc/sys/fs/binfmt_misc/WSLInterop ]; then
    echo "Running in WSL..."
    
    # Navigate to project
    cd /mnt/t/Python/cc_mobile 2>/dev/null || cd "$(dirname "$0")"
    
    # Check if venv exists, create if not
    if [ ! -d ~/venvs/cc_mobile ]; then
        echo "Virtual environment not found. Creating it..."
        mkdir -p ~/venvs
        python3 -m venv ~/venvs/cc_mobile
        source ~/venvs/cc_mobile/bin/activate
        pip install --upgrade pip setuptools wheel
        echo "Installing dependencies..."
        pip install -r requirements.txt
    else
        source ~/venvs/cc_mobile/bin/activate
    fi
    
    # Start server
    python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    
else
    # Running from Windows - launch WSL
    echo "Detected Windows environment. Launching WSL..."
    wsl bash -c "cd /mnt/t/Python/cc_mobile && bash run_wsl.sh"
fi

