#!/usr/bin/env bash

# 1. Update core tools to avoid build errors
echo "Step 1: Upgrading core packaging tools..."
pip install --upgrade pip setuptools wheel

# 2. Install modern, clean numerical dependencies (Pandas, Numpy, Scipy).
# This is the stable, modern version xai needs to use instead of 0.23.4.
echo "Step 2: Installing core numerical libraries (Pandas 2.1.4)..."
pip install numpy pandas==2.1.4 scipy

# 3. Install xai (and other former conflict packages) using the --no-deps flag.
# This is the critical step that bypasses xai's restrictive, broken dependency check.
echo "Step 3: Installing conflicting packages using --no-deps..."
pip install xai --no-deps  # <-- Forces xai to use pandas from Step 2
pip install oci --no-deps
pip install uvicorn --no-deps

# 4. Install the remaining non-conflicting packages from the minimalist list
echo "Step 4: Installing remaining packages from requirements.txt..."
pip install -r requirements.txt

# Example build command in Render settings:
chmod 600 oci_api_key.pem

echo "Build process complete!"