#!/usr/bin/env bash

# 1. Update core tools to avoid build errors
pip install --upgrade pip setuptools wheel

# 2. Install core numerical libraries with a specific, stable Pandas version.
# This version avoids the known metadata bug.
pip install numpy scipy pandas==1.5.3

# 3. Install packages that conflict with dependencies (no-deps flag)
# They will now use the stable Pandas version installed in Step 2.
pip install gradio --no-deps
pip install oci --no-deps
pip install fastapi --no-deps
pip install uvicorn --no-deps

# 4. Install the remaining non-conflicting packages from the minimal list
pip install -r requirements.txt