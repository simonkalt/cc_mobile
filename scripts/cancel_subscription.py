#!/usr/bin/env python3
"""
Script to cancel a user's subscription via the API.

This script:
1. Prompts for user_id
2. Prompts for cancel_immediately flag (cancel now vs at period end)
3. Prompts for JWT access token (or reads from environment)
4. Makes API call to cancel the subscription
5. Displays the result

Usage:
    python scripts/cancel_subscription.py

    Or set environment variables:
    - API_BASE_URL (default: http://localhost:8000)
    - JWT_ACCESS_TOKEN (optional - will prompt if not set)
"""

import sys
import os
import json
import re
from pathlib import Path

# Add parent directory to path to import app modules (for config)
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from dotenv import load_dotenv
from app.core.config import settings

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
CANCEL_ENDPOINT = f"{API_BASE_URL}/api/subscriptions/cancel"


def get_user_input(prompt: str, default: str = None) -> str:
    """Get user input with optional default value."""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "

    user_input = input(full_prompt).strip()
    return user_input if user_input else default


def get_yes_no_input(prompt: str, default: bool = False) -> bool:
    """Get yes/no input from user."""
    default_str = "Y/n" if default else "y/N"
    full_prompt = f"{prompt} [{default_str}]: "

    while True:
        user_input = input(full_prompt).strip().lower()

        if not user_input:
            return default

        if user_input in ["y", "yes"]:
            return True
        elif user_input in ["n", "no"]:
            return False
        else:
            print("Please enter 'y' or 'n' (or 'yes' or 'no')")


def clean_token_input(token_input: str) -> str:
    """
    Clean and extract JWT token from user input.

    Handles various input formats:
    - Plain token: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    - Quoted token: '"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."'
    - JSON object: '{"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'
    - JSON with key: '"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."'

    Args:
        token_input: Raw token input from user

    Returns:
        Cleaned token string
    """
    if not token_input:
        return ""

    token = token_input.strip()

    # Try to parse as JSON object first
    try:
        # If it's a complete JSON object
        if token.startswith("{") and token.endswith("}"):
            parsed = json.loads(token)
            if "access_token" in parsed:
                return parsed["access_token"]
            # Try other common key names
            for key in ["accessToken", "token", "jwt", "jwt_token"]:
                if key in parsed:
                    return parsed[key]
    except (json.JSONDecodeError, ValueError):
        pass

    # Try to extract from JSON-like string (e.g., '"access_token": "token"')
    if '"access_token"' in token or "'access_token'" in token:
        # Try to extract the value after the colon
        match = re.search(r'["\']access_token["\']\s*:\s*["\']([^"\']+)["\']', token)
        if match:
            return match.group(1)

    # Remove surrounding quotes if present
    if (token.startswith('"') and token.endswith('"')) or (
        token.startswith("'") and token.endswith("'")
    ):
        token = token[1:-1]

    # Remove any trailing commas or semicolons
    token = token.rstrip(",;")

    return token.strip()


def cancel_subscription_api(user_id: str, cancel_immediately: bool, access_token: str) -> dict:
    """
    Cancel subscription via API.

    Args:
        user_id: User ID to cancel subscription for
        cancel_immediately: If True, cancel immediately; if False, cancel at period end
        access_token: JWT access token for authentication

    Returns:
        Response dictionary from API
    """
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}

    payload = {"user_id": user_id, "cancel_immediately": cancel_immediately}

    print(f"\nMaking API request to: {CANCEL_ENDPOINT}")
    print(f"User ID: {user_id}")
    print(f"Cancel immediately: {cancel_immediately}")
    print()

    try:
        response = requests.post(CANCEL_ENDPOINT, headers=headers, json=payload, timeout=30)

        # Try to parse JSON response
        try:
            response_data = response.json()
        except ValueError:
            response_data = {"raw_response": response.text}

        return {
            "status_code": response.status_code,
            "success": response.status_code == 200,
            "data": response_data,
            "headers": dict(response.headers),
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "status_code": None,
            "success": False,
            "error": f"Connection error: {e}",
            "message": f"Could not connect to API at {API_BASE_URL}. Is the server running?",
        }
    except requests.exceptions.Timeout as e:
        return {
            "status_code": None,
            "success": False,
            "error": f"Request timeout: {e}",
            "message": "The API request took too long to complete.",
        }
    except requests.exceptions.RequestException as e:
        return {
            "status_code": None,
            "success": False,
            "error": f"Request error: {e}",
            "message": f"An error occurred while making the API request: {e}",
        }
    except Exception as e:
        return {
            "status_code": None,
            "success": False,
            "error": f"Unexpected error: {e}",
            "message": f"An unexpected error occurred: {e}",
        }


def main():
    """Main function to run the subscription cancellation script."""
    print("=" * 70)
    print("Subscription Cancellation Script")
    print("=" * 70)
    print()
    print(f"API Base URL: {API_BASE_URL}")
    print()

    # Get user_id
    user_id = get_user_input("Enter user ID to cancel subscription for")
    if not user_id:
        print("Error: User ID is required.")
        sys.exit(1)

    # Get cancel_immediately flag
    print()
    print("Cancel immediately?")
    print("  - Yes: Subscription will be canceled immediately")
    print("  - No: Subscription will be canceled at the end of the current billing period")
    cancel_immediately = get_yes_no_input("Cancel immediately", default=False)

    # Get access token
    print()
    access_token = os.getenv("JWT_ACCESS_TOKEN")
    if not access_token:
        print("JWT access token not found in environment variables.")
        print("You can set JWT_ACCESS_TOKEN in your .env file or enter it now.")
        print(
            "(You can paste the token directly, or paste a JSON response with 'access_token' field)"
        )
        token_input = get_user_input("Enter JWT access token")
        if not token_input:
            print("Error: JWT access token is required for authentication.")
            sys.exit(1)
        access_token = clean_token_input(token_input)
        if not access_token:
            print(
                "Error: Could not extract valid token from input. Please enter just the token value."
            )
            sys.exit(1)
    else:
        print(f"Using JWT access token from environment (length: {len(access_token)} characters)")
        use_env_token = get_yes_no_input("Use this token", default=True)
        if not use_env_token:
            print(
                "(You can paste the token directly, or paste a JSON response with 'access_token' field)"
            )
            token_input = get_user_input("Enter JWT access token")
            if not token_input:
                print("Error: JWT access token is required for authentication.")
                sys.exit(1)
            access_token = clean_token_input(token_input)
            if not access_token:
                print(
                    "Error: Could not extract valid token from input. Please enter just the token value."
                )
                sys.exit(1)

    # Make API call
    print()
    print("=" * 70)
    result = cancel_subscription_api(user_id, cancel_immediately, access_token)

    # Display results
    print("=" * 70)
    print("RESULT:")
    print("=" * 70)

    if result.get("success"):
        print("✅ Subscription canceled successfully!")
        print()
        if "data" in result:
            print("Response data:")
            print(json.dumps(result["data"], indent=2))
    else:
        print("❌ Failed to cancel subscription")
        print()
        if "status_code" in result and result["status_code"]:
            print(f"HTTP Status Code: {result['status_code']}")
        if "error" in result:
            print(f"Error: {result['error']}")
        if "message" in result:
            print(f"Message: {result['message']}")
        if "data" in result:
            print("\nResponse data:")
            print(json.dumps(result["data"], indent=2))

    print("=" * 70)

    # Exit with appropriate code
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
