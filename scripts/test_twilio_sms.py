#!/usr/bin/env python3
"""
Test script for Twilio SMS sending functionality.

This script prompts for a phone number and sends a test SMS message
to verify that Twilio is properly configured and working.

Usage:
    python scripts/test_twilio_sms.py
    # or
    ./scripts/test_twilio_sms.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from app.utils.sms_utils import send_sms, normalize_phone_number
from app.core.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def clean_phone_input(phone: str) -> str:
    """
    Clean phone number input from user.
    Handles various formats and extracts just the phone number.
    
    Args:
        phone: Raw phone number input (may include quotes, JSON, etc.)
        
    Returns:
        Cleaned phone number string
    """
    # Remove quotes if present
    phone = phone.strip().strip('"').strip("'")
    
    # Remove JSON wrapper if present
    if phone.startswith('{') and phone.endswith('}'):
        import json
        try:
            data = json.loads(phone)
            phone = data.get('phone', data.get('phone_number', phone))
        except:
            pass
    
    return phone.strip()


def main():
    """Main function to test Twilio SMS sending."""
    print("=" * 60)
    print("Twilio SMS Test Script")
    print("=" * 60)
    print()
    
    # Check Twilio configuration
    print("Checking Twilio configuration...")
    if not settings.TWILIO_ACCOUNT_SID:
        print("❌ ERROR: TWILIO_ACCOUNT_SID not configured")
        print("   Please set this environment variable or add it to your .env file")
        return 1
    
    if not settings.TWILIO_AUTH_TOKEN:
        print("❌ ERROR: TWILIO_AUTH_TOKEN not configured")
        print("   Please set this environment variable or add it to your .env file")
        return 1
    
    if not settings.TWILIO_PHONE_NUMBER:
        print("❌ ERROR: TWILIO_PHONE_NUMBER not configured")
        print("   Please set this environment variable or add it to your .env file")
        return 1
    
    print("✓ Twilio configuration found")
    print(f"  Account SID: {settings.TWILIO_ACCOUNT_SID[:10]}...")
    print(f"  From Number: {settings.TWILIO_PHONE_NUMBER}")
    print()
    
    # Prompt for phone number
    print("Enter the phone number to send a test SMS to:")
    print("  Format examples: +1234567890, (123) 456-7890, 123-456-7890")
    print("  (The script will normalize the format automatically)")
    print()
    
    phone_input = input("Phone number: ").strip()
    
    if not phone_input:
        print("❌ ERROR: Phone number cannot be empty")
        return 1
    
    # Clean and normalize phone number
    try:
        cleaned_phone = clean_phone_input(phone_input)
        normalized_phone = normalize_phone_number(cleaned_phone)
        print(f"  Normalized phone number: {normalized_phone}")
        print()
    except Exception as e:
        print(f"❌ ERROR: Failed to normalize phone number: {e}")
        return 1
    
    # Prompt for custom message (optional)
    print("Enter a custom message (or press Enter for default test message):")
    custom_message = input("Message: ").strip()
    
    if not custom_message:
        custom_message = (
            "This is a test message from the Cover Letter API. "
            "If you received this, Twilio SMS is working correctly! 🎉"
        )
    
    print()
    print("=" * 60)
    print("Sending SMS...")
    print("=" * 60)
    print(f"To: {normalized_phone}")
    print(f"From: {settings.TWILIO_PHONE_NUMBER}")
    print(f"Message: {custom_message}")
    print()
    
    # Send SMS
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
            print("  1. Twilio credentials are correct")
            print("  2. Twilio phone number is verified and active")
            print("  3. Recipient phone number is valid")
            print("  4. Your Twilio account has sufficient balance")
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

