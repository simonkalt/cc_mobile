#!/usr/bin/env python3
"""Quick script to check if redis is importable"""
import sys

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.path[:3]}...")

try:
    import redis
    print(f"✓ redis imported successfully")
    print(f"  redis version: {redis.__version__ if hasattr(redis, '__version__') else 'unknown'}")
    print(f"  redis module path: {redis.__file__}")
except ImportError as e:
    print(f"✗ Failed to import redis: {e}")
    sys.exit(1)

