#!/usr/bin/env python3
"""
Email sending test script
Tests the email sending functionality with SMTP2Go

Usage:
    python test_email.py --to user@example.com --code 123456
    python test_email.py -t user@example.com -c 123456
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

try:
    from app.utils.email_utils import send_verification_code_email, EMAIL_AVAILABLE
    from app.core.config import settings
except ImportError as e:
    logger.error(f"Failed to import email utilities: {e}")
    sys.exit(1)


def test_email_sending(to_email: str, code: str):
    """
    Test sending a verification code email
    
    Args:
        to_email: Recipient email address
        code: 6-digit verification code
    """
    logger.info("=" * 80)
    logger.info("Email Sending Test")
    logger.info("=" * 80)
    
    # Validate code format
    if not code.isdigit() or len(code) != 6:
        logger.error(f"Invalid code format: {code}. Must be a 6-digit number.")
        return False
    
    # Check SMTP configuration
    logger.info("Checking SMTP configuration...")
    logger.info(f"  SMTP Server: {settings.SMTP_SERVER}")
    logger.info(f"  SMTP Port: {settings.SMTP_PORT}")
    logger.info(f"  SMTP Username: {settings.SMTP_USERNAME}")
    logger.info(f"  SMTP Use TLS: {settings.SMTP_USE_TLS}")
    logger.info(f"  SMTP Use SSL: {settings.SMTP_USE_SSL}")
    logger.info(f"  From Email: {settings.FROM_EMAIL}")
    logger.info(f"  Email Available: {EMAIL_AVAILABLE}")
    
    if not EMAIL_AVAILABLE:
        logger.error("❌ SMTP is not configured. Please check your .env file.")
        logger.error("Required variables: SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD")
        return False
    
    if not settings.FROM_EMAIL:
        logger.error("❌ FROM_EMAIL is not configured. Please set it in your .env file.")
        return False
    
    logger.info("")
    logger.info(f"Sending verification code email to: {to_email}")
    logger.info(f"Verification code: {code}")
    logger.info("")
    
    # Test different purposes
    purposes = [
        ("finish_registration", "Registration Verification Code"),
        ("forgot_password", "Password Reset Verification Code"),
        ("change_password", "Password Change Verification Code"),
        ("verification", "Verification Code"),
    ]
    
    success_count = 0
    total_tests = len(purposes)
    
    for purpose, description in purposes:
        logger.info(f"Testing: {description} (purpose: {purpose})")
        try:
            result = send_verification_code_email(to_email, code, purpose)
            if result:
                logger.info(f"  ✓ Email sent successfully for {purpose}")
                success_count += 1
            else:
                logger.error(f"  ✗ Failed to send email for {purpose}")
        except Exception as e:
            logger.error(f"  ✗ Error sending email for {purpose}: {e}", exc_info=True)
        logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("Test Summary")
    logger.info("=" * 80)
    logger.info(f"Total tests: {total_tests}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {total_tests - success_count}")
    
    if success_count == total_tests:
        logger.info("✓ All email tests passed!")
        return True
    else:
        logger.warning(f"⚠ Some email tests failed ({total_tests - success_count} out of {total_tests})")
        return False


def main():
    """Main function to parse arguments and run tests"""
    parser = argparse.ArgumentParser(
        description="Test email sending functionality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_email.py --to user@example.com --code 123456
  python test_email.py -t user@example.com -c 000000
        """
    )
    
    parser.add_argument(
        "--to", "-t",
        type=str,
        required=True,
        help="Recipient email address"
    )
    
    parser.add_argument(
        "--code", "-c",
        type=str,
        required=True,
        help="6-digit verification code"
    )
    
    args = parser.parse_args()
    
    # Run the test
    success = test_email_sending(args.to, args.code)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

