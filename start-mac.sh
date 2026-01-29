#!/bin/bash
# start_mac.sh

cd "$(dirname "$0")"

# Activate venv
source .venv/bin/activate

# Start FastAPI server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
