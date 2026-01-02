#!/usr/bin/env python3
"""
Test script to fetch Stripe products and prices
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

print("=== Fetching Products ===")
products_response = requests.get(
    "https://api.stripe.com/v1/products",
    auth=(STRIPE_KEY, ""),
    params={"active": True, "limit": 100},
)

if products_response.status_code != 200:
    print(f"❌ Error fetching products: {products_response.status_code}")
    print(products_response.text)
    sys.exit(1)

products_data = products_response.json()

# Log full JSON response
print()
print("=== Full Products JSON Response ===")
print(json.dumps(products_data, indent=2))

print()
print("=== Parsed Products Summary ===")
products = products_data.get("data", [])
print(f"Found {len(products)} products:")
print()

for product in products:
    print(f"Product: {product.get('id')} - {product.get('name')} (active: {product.get('active')})")
    metadata = product.get("metadata", {})
    if metadata:
        print("  Metadata:")
        for key, value in metadata.items():
            print(f"    {key}: {value}")
        # Check specifically for features
        if "features" in metadata:
            print('  ✅ FEATURES FOUND in metadata["features"]:')
            features = metadata["features"]
            # Try to parse as JSON array, otherwise split by comma
            try:
                if features.startswith("["):
                    features_list = json.loads(features)
                else:
                    features_list = [f.strip() for f in features.split(",")]
                for i, feature in enumerate(features_list, 1):
                    print(f"    {i}. {feature}")
            except:
                print(f"    {features}")
        else:
            print('  ⚠️  No "features" key found in metadata')
    else:
        print("  ⚠️  No metadata found for this product")
    print()

print()
print("=== Fetching All Prices (All Types) ===")
prices_response = requests.get(
    "https://api.stripe.com/v1/prices",
    auth=(STRIPE_KEY, ""),
    params={"active": True, "limit": 100},
)

if prices_response.status_code != 200:
    print(f"❌ Error fetching prices: {prices_response.status_code}")
    print(prices_response.text)
    sys.exit(1)

prices_data = prices_response.json()

# Log full JSON response
print()
print("=== Full Prices JSON Response ===")
print(json.dumps(prices_data, indent=2))

print()
print("=== Parsed Prices Summary ===")
all_prices = prices_data.get("data", [])
recurring = [p for p in all_prices if p.get("type") == "recurring"]
one_time = [p for p in all_prices if p.get("type") == "one_time"]

print(f"Found {len(all_prices)} total prices:")
print(f"  - {len(recurring)} recurring prices")
print(f"  - {len(one_time)} one-time prices")
print()

print("=== All Prices ===")
for price in all_prices:
    price_type = price.get("type", "unknown")
    amount = price.get("unit_amount", 0) / 100 if price.get("unit_amount") else 0
    currency = price.get("currency", "usd").upper()
    active = price.get("active", False)

    if price_type == "recurring":
        recurring_info = price.get("recurring", {})
        interval = recurring_info.get("interval", "unknown")
        print(
            f"  [{price_type.upper()}] {price.get('id')}: Product {price.get('product')}, {interval}ly, ${amount:.2f} {currency} (active: {active})"
        )
    else:
        print(
            f"  [{price_type.upper()}] {price.get('id')}: Product {price.get('product')}, ${amount:.2f} {currency} (active: {active})"
        )

