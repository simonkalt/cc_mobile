#!/usr/bin/env python3
"""
Test script to fetch Stripe products with full JSON response
Reads Stripe API key from .env file
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Get Stripe API key from environment (prioritize production key)
STRIPE_KEY = os.getenv("STRIPE_API_KEY") or os.getenv("STRIPE_TEST_API_KEY")

if not STRIPE_KEY:
    print("❌ Error: STRIPE_API_KEY or STRIPE_TEST_API_KEY not found in .env file")
    sys.exit(1)

print("==========================================")
print("Stripe Products Fetch")
print("==========================================")
print()

# Fetch products
print("Fetching active products from Stripe...")
response = requests.get(
    "https://api.stripe.com/v1/products",
    auth=(STRIPE_KEY, ""),
    params={"active": True, "limit": 100},
)

if response.status_code != 200:
    print(f"❌ Error fetching products: {response.status_code}")
    print(response.text)
    sys.exit(1)

products_data = response.json()

# Check if we got a valid response
if "data" not in products_data:
    print("❌ Error: Invalid response format")
    print(products_data)
    sys.exit(1)

print("✅ Successfully fetched products")

print()
print("==========================================")
print("Full Products JSON Response")
print("==========================================")
print(json.dumps(products_data, indent=2))

