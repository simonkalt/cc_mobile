#!/bin/bash
# Verify pymupdf installation in WSL
# Run this from WSL terminal

echo "Verifying pymupdf installation..."

cd /mnt/t/Python/cc_mobile || cd "$(dirname "$0")"

# Try to use the venv's Python directly
if [ -f ".venv/bin/python3" ]; then
    echo "Testing with venv Python..."
    .venv/bin/python3 -c "
import sys
try:
    import fitz
    print('✓ pymupdf (fitz) imported successfully!')
    print(f'  Version: {fitz.version[0] if hasattr(fitz, \"version\") else \"unknown\"}')
    
    # Test basic functionality
    print('✓ Basic import test passed')
    sys.exit(0)
except ImportError as e:
    print(f'✗ Import failed: {e}')
    sys.exit(1)
except Exception as e:
    print(f'✗ Error: {e}')
    sys.exit(1)
"
elif [ -f ".venv/bin/python" ]; then
    echo "Testing with venv Python..."
    .venv/bin/python -c "
import sys
try:
    import fitz
    print('✓ pymupdf (fitz) imported successfully!')
    print(f'  Version: {fitz.version[0] if hasattr(fitz, \"version\") else \"unknown\"}')
    sys.exit(0)
except Exception as e:
    print(f'✗ Error: {e}')
    sys.exit(1)
"
else
    echo "⚠️  Could not find venv Python executable"
    echo "Library files are present, but cannot test import"
    echo "Files found:"
    ls -la .venv/lib/python3.12/site-packages/ | grep -i "fitz\|pymupdf" | head -5
fi

