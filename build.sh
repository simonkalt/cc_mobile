#!/usr/bin/env bash

# 1. Update core tools to avoid build errors
pip install --upgrade pip setuptools wheel

# 2. Install packages that conflict with dependencies (no-deps flag)
# This forces them to look for dependencies later, after we install clean ones.
pip install gradio --no-deps
pip install oci --no-deps
pip install fastapi --no-deps
pip install uvicorn --no-deps

# 3. Install core numerical libraries with explicit, modern, stable versions.
# This ensures a modern, clean version of pandas is available for the packages
# installed in Step 2 to link against.
pip install numpy pandas==2.1.4 scipy

# 4. Install the remaining non-conflicting packages from the minimal list
pip install -r requirements.txt