#!/usr/bin/env python3
"""
Test script for Telnyx SMS sending functionality.

This script prompts for a phone number and sends a test SMS message
to verify that Telnyx is properly configured and working.

Usage:
    python scripts/test_telnyx_sms.py
    # or
    ./scripts/test_telnyx_sms.py
"""

import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from app.utils.sms_utils import send_sms, normalize_phone_number
from app.core.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def clean_phone_input(phone: str) -> str:
    """
    Clean phone number input from user.
    Handles various formats and extracts just the phone number.
    """
    phone = phone.strip().strip('"').strip("'")

    if phone.startswith("{") and phone.endswith("}"):
        import json

        try:
            data = json.loads(phone)
            phone = data.get("phone", data.get("phone_number", phone))
        except Exception:
            pass

    return phone.strip()


def main():
    """Main function to test Telnyx SMS sending."""
    print("=" * 60)
    print("Telnyx SMS Test Script")
    print("=" * 60)
    print()

    print("Checking Telnyx configuration...")
    if not settings.TELNYX_API_KEY:
        print("❌ ERROR: TELNYX_API_KEY not configured")
        print("   Please set this environment variable or add it to your .env file")
        return 1

    if not settings.TELNYX_PHONE_NUMBER:
        print("❌ ERROR: TELNYX_PHONE_NUMBER not configured")
        print("   Please set this environment variable or add it to your .env file")
        return 1

    print("✓ Telnyx configuration found")
    print(f"  API Key: {settings.TELNYX_API_KEY}...")
    print(f"  From Number: {settings.TELNYX_PHONE_NUMBER}")
    print()

    print("Enter the phone number to send a test SMS to:")
    print("  Format examples: +1234567890, (123) 456-7890, 123-456-7890")
    print("  (The script will normalize the format automatically)")
    print()

    phone_input = input("Phone number: ").strip()

    if not phone_input:
        print("❌ ERROR: Phone number cannot be empty")
        return 1

    try:
        cleaned_phone = clean_phone_input(phone_input)
        normalized_phone = normalize_phone_number(cleaned_phone)
        print(f"  Normalized phone number: {normalized_phone}")
        print()
    except Exception as e:
        print(f"❌ ERROR: Failed to normalize phone number: {e}")
        return 1

    print("Enter a custom message (or press Enter for default test message):")
    custom_message = input("Message: ").strip()

    if not custom_message:
        custom_message = (
            "This is a test message from the Cover Letter API. "
            "If you received this, Telnyx SMS is working correctly! 🎉"
        )

    print()
    print("=" * 60)
    print("Sending SMS...")
    print("=" * 60)
    print(f"To: {normalized_phone}")
    print(f"From: {settings.TELNYX_PHONE_NUMBER}")
    print(f"Message: {custom_message}")
    print()

    try:
        success = send_sms(normalized_phone, custom_message)

        if success:
            print("=" * 60)
            print("✓ SUCCESS: SMS sent successfully!")
            print("=" * 60)
            print()
            print(f"Check the phone {normalized_phone} for the test message.")
            print()
            return 0
        else:
            print("=" * 60)
            print("❌ ERROR: Failed to send SMS")
            print("=" * 60)
            print()
            print("Please check:")
            print("  1. Telnyx API key is correct")
            print("  2. Telnyx phone number is on an active messaging profile")
            print("  3. Recipient phone number is valid (E.164)")
            print("  4. Your Telnyx account has sufficient balance")
            print("  5. Check the logs above for detailed error messages")
            print()
            return 1

    except KeyboardInterrupt:
        print()
        print("❌ Cancelled by user")
        return 1
    except Exception as e:
        print()
        print(f"❌ ERROR: Unexpected error: {e}")
        logger.exception("Unexpected error sending SMS")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        logger.exception("Fatal error in test script")
        sys.exit(1)
