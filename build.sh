#!/usr/bin/env bash

# Step 1: Install core build requirements (as wheels)
pip install --upgrade pip setuptools wheel numpy scipy

# Step 2: Run the custom installation steps to handle conflicts
pip install oci --no-deps
pip install fastapi --no-deps
pip install uvicorn --no-deps

# Step 3: Install the rest from the minimal requirements.txt
pip install -r requirements.txt