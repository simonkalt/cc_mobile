#!/usr/bin/env python3
"""
Comprehensive test script for Redis server integration.

This script tests:
- Redis library availability
- Connection configuration
- Basic connection (ping)
- Registration data operations (store, get, delete)
- Verification session operations (store, get, delete)
- TTL (Time To Live) functionality
- Error handling

Usage:
    python tests/test_redis_integration.py
"""

import sys
import time
import json
import socket
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.utils import redis_utils


class Colors:
    """ANSI color codes for terminal output"""

    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}\n")


def print_test(test_name: str):
    """Print a test name"""
    print(f"{Colors.BLUE}→ Testing: {test_name}{Colors.RESET}")


def print_success(message: str):
    """Print a success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print an error message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_warning(message: str):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


def print_info(message: str):
    """Print an info message"""
    print(f"  {message}")


def test_redis_library():
    """Test 1: Check if Redis library is available"""
    print_test("Redis library availability")

    if redis_utils.REDIS_AVAILABLE:
        print_success("Redis library is installed")
        try:
            import redis

            version = getattr(redis, "__version__", "unknown")
            print_info(f"Redis version: {version}")
            return True
        except Exception as e:
            print_error(f"Error importing redis: {e}")
            return False
    else:
        print_error("Redis library is not installed")
        print_info("Install with: pip install redis")
        return False


def test_redis_configuration():
    """Test 2: Check Redis configuration"""
    print_test("Redis configuration")

    config_ok = True

    if not settings.REDIS_HOST:
        print_error("REDIS_HOST is not configured")
        config_ok = False
    else:
        print_success(f"REDIS_HOST: {settings.REDIS_HOST}")

    print_info(f"REDIS_PORT: {settings.REDIS_PORT}")
    print_info(f"REDIS_DB: {settings.REDIS_DB}")
    print_info(f"REDIS_SSL: {settings.REDIS_SSL}")

    if settings.REDIS_USERNAME:
        print_info(f"REDIS_USERNAME: {settings.REDIS_USERNAME}")
    else:
        print_warning("REDIS_USERNAME not set (optional)")

    if settings.REDIS_PASSWORD:
        print_info("REDIS_PASSWORD: *** (configured)")
    else:
        print_warning("REDIS_PASSWORD not set (may be required)")

    return config_ok


def test_dns_resolution():
    """Test 2.5: Test DNS resolution for Redis host"""
    print_test("DNS resolution")

    if not settings.REDIS_HOST:
        print_error("Cannot test DNS - REDIS_HOST not configured")
        return False

    try:
        print_info(f"Resolving hostname: {settings.REDIS_HOST}")
        ip_address = socket.gethostbyname(settings.REDIS_HOST)
        print_success(f"DNS resolution successful: {settings.REDIS_HOST} -> {ip_address}")
        return True
    except socket.gaierror as e:
        error_code = e.args[0] if e.args else "unknown"
        error_msg = e.args[1] if len(e.args) > 1 else str(e)

        if error_code == 11001 or "getaddrinfo failed" in str(e).lower():
            print_error(f"DNS resolution failed (Error 11001): {error_msg}")
            print_info("This usually means:")
            print_info("  - The hostname cannot be resolved by DNS")
            print_info("  - Network connectivity issues")
            print_info("  - Firewall blocking DNS queries")
            print_info("  - VPN or proxy configuration issues")
        else:
            print_error(f"DNS resolution failed: {error_msg} (code: {error_code})")
        return False
    except Exception as e:
        print_error(f"Unexpected error during DNS resolution: {e}")
        return False


def test_network_connectivity():
    """Test 2.6: Test network connectivity to Redis host and port"""
    print_test("Network connectivity")

    if not settings.REDIS_HOST:
        print_error("Cannot test connectivity - REDIS_HOST not configured")
        return False

    try:
        print_info(f"Testing connection to {settings.REDIS_HOST}:{settings.REDIS_PORT}")

        # Create a socket and set timeout
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout

        try:
            result = sock.connect_ex((settings.REDIS_HOST, settings.REDIS_PORT))
            sock.close()

            if result == 0:
                print_success(
                    f"Network connectivity successful to {settings.REDIS_HOST}:{settings.REDIS_PORT}"
                )
                return True
            else:
                print_error(f"Connection failed (error code: {result})")
                print_info("This usually means:")
                print_info("  - Port is blocked by firewall")
                print_info("  - Host is not reachable")
                print_info("  - Service is not running on that port")
                return False
        except socket.timeout:
            sock.close()
            print_error("Connection timeout - host may be unreachable or port blocked")
            return False
        except Exception as e:
            sock.close()
            print_error(f"Connection error: {e}")
            return False

    except socket.gaierror as e:
        print_error(f"Cannot resolve hostname: {e}")
        print_info("DNS resolution must succeed before testing connectivity")
        return False
    except Exception as e:
        print_error(f"Unexpected error testing connectivity: {e}")
        return False


def test_redis_connection():
    """Test 3: Test Redis connection"""
    print_test("Redis connection")

    try:
        client = redis_utils.get_redis_client()
        client.ping()
        print_success("Successfully connected to Redis")
        print_info(f"Connected to: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        return True
    except ImportError as e:
        print_error(f"Redis library not available: {e}")
        return False
    except ConnectionError as e:
        error_str = str(e)
        print_error(f"Connection failed: {error_str}")

        # Provide specific diagnostics based on error
        if "11001" in error_str or "getaddrinfo failed" in error_str.lower():
            print_info("\nDiagnostic information:")
            print_info("  Error 11001 = DNS resolution failure (WSAHOST_NOT_FOUND)")
            print_info("  Possible causes:")
            print_info("    1. Hostname cannot be resolved by DNS")
            print_info("    2. Network connectivity issues")
            print_info("    3. VPN required but not connected")
            print_info("    4. Firewall blocking DNS queries")
            print_info("    5. Incorrect REDIS_HOST configuration")
            print_info("\n  Troubleshooting steps:")
            print_info("    1. Verify REDIS_HOST is correct in .env file")
            print_info("    2. Try: ping <REDIS_HOST> (from command prompt)")
            print_info("    3. Try: nslookup <REDIS_HOST> (from command prompt)")
            print_info("    4. Check if VPN is required and connected")
            print_info("    5. Verify network/firewall settings")
        elif "timeout" in error_str.lower():
            print_info("\nDiagnostic information:")
            print_info("  Connection timeout - host may be unreachable")
            print_info("  Possible causes:")
            print_info("    1. Firewall blocking the port")
            print_info("    2. Host is down or unreachable")
            print_info("    3. Network routing issues")
        elif "refused" in error_str.lower() or "connection refused" in error_str.lower():
            print_info("\nDiagnostic information:")
            print_info("  Connection refused - port may be closed or service not running")
            print_info("  Possible causes:")
            print_info("    1. Redis service is not running")
            print_info("    2. Wrong port number")
            print_info("    3. Firewall blocking the connection")

        return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback

        print_info("Full traceback:")
        traceback.print_exc()
        return False


def test_redis_availability():
    """Test 4: Test is_redis_available() function"""
    print_test("Redis availability check")

    try:
        is_available = redis_utils.is_redis_available()
        if is_available:
            print_success("Redis is available")
            return True
        else:
            print_error("Redis is not available")
            return False
    except Exception as e:
        print_error(f"Error checking availability: {e}")
        return False


def test_registration_data_operations():
    """Test 5: Test registration data operations (store, get, delete)"""
    print_test("Registration data operations")

    test_email = "test@example.com"
    test_code = "123456"
    test_data = {
        "name": "Test User",
        "email": test_email,
        "phone": "123-456-7890",
        "password": "hashed_password_here",
        "preferences": {"theme": "dark"},
    }

    try:
        # Test store
        print_info("Storing registration data...")
        stored = redis_utils.store_registration_data(
            email=test_email, code=test_code, registration_data=test_data, ttl_minutes=5
        )
        if not stored:
            print_error("Failed to store registration data")
            return False
        print_success("Registration data stored")

        # Test get
        print_info("Retrieving registration data...")
        retrieved = redis_utils.get_registration_data(email=test_email, code=test_code)
        if not retrieved:
            print_error("Failed to retrieve registration data")
            return False

        # Verify data matches
        if retrieved.get("name") != test_data["name"]:
            print_error("Retrieved data doesn't match stored data")
            return False
        print_success("Registration data retrieved and verified")

        # Test delete
        print_info("Deleting registration data...")
        deleted = redis_utils.delete_registration_data(email=test_email, code=test_code)
        if not deleted:
            print_error("Failed to delete registration data")
            return False
        print_success("Registration data deleted")

        # Verify deletion
        retrieved_after_delete = redis_utils.get_registration_data(email=test_email, code=test_code)
        if retrieved_after_delete is not None:
            print_error("Data still exists after deletion")
            return False
        print_success("Deletion verified")

        return True

    except Exception as e:
        print_error(f"Error in registration data operations: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_verification_session_operations():
    """Test 6: Test verification session operations (store, get, delete)"""
    print_test("Verification session operations")

    test_email = "test@example.com"
    test_code = "654321"
    test_purpose = "finish_registration"
    test_phone = "123-456-7890"

    try:
        # Test store
        print_info("Storing verification session...")
        stored = redis_utils.store_verification_session(
            email=test_email,
            code=test_code,
            purpose=test_purpose,
            phone=test_phone,
            delivery_method="sms",
            ttl_minutes=5,
        )
        if not stored:
            print_error("Failed to store verification session")
            return False
        print_success("Verification session stored")

        # Test get
        print_info("Retrieving verification session...")
        retrieved = redis_utils.get_verification_session(
            email=test_email, code=test_code, purpose=test_purpose
        )
        if not retrieved:
            print_error("Failed to retrieve verification session")
            return False

        # Verify data matches
        if retrieved.get("email") != test_email:
            print_error("Retrieved session data doesn't match stored data")
            return False
        if retrieved.get("purpose") != test_purpose:
            print_error("Retrieved session purpose doesn't match")
            return False
        print_success("Verification session retrieved and verified")

        # Test delete
        print_info("Deleting verification session...")
        deleted = redis_utils.delete_verification_session(
            email=test_email, code=test_code, purpose=test_purpose
        )
        if not deleted:
            print_error("Failed to delete verification session")
            return False
        print_success("Verification session deleted")

        # Verify deletion
        retrieved_after_delete = redis_utils.get_verification_session(
            email=test_email, code=test_code, purpose=test_purpose
        )
        if retrieved_after_delete is not None:
            print_error("Session still exists after deletion")
            return False
        print_success("Deletion verified")

        return True

    except Exception as e:
        print_error(f"Error in verification session operations: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_ttl_functionality():
    """Test 7: Test TTL (Time To Live) functionality"""
    print_test("TTL functionality")

    test_email = "ttl_test@example.com"
    test_code = "999999"
    test_data = {"name": "TTL Test User", "email": test_email, "password": "hashed_password"}

    try:
        # Store with short TTL (10 seconds)
        print_info("Storing data with 10 second TTL...")
        stored = redis_utils.store_registration_data(
            email=test_email,
            code=test_code,
            registration_data=test_data,
            ttl_minutes=0,  # We'll use a custom TTL via client
        )

        # Use client directly to set custom TTL
        client = redis_utils.get_redis_client()
        key = f"registration:{test_email}:{test_code}"
        client.setex(key, 10, json.dumps(test_data))  # 10 seconds

        # Verify data exists
        retrieved = redis_utils.get_registration_data(test_email, test_code)
        if not retrieved:
            print_error("Data not found immediately after storing")
            return False
        print_success("Data stored and retrieved")

        # Check TTL
        ttl = client.ttl(key)
        print_info(f"TTL remaining: {ttl} seconds")

        # Wait for expiration (12 seconds to be safe)
        print_info("Waiting for TTL expiration (12 seconds)...")
        time.sleep(12)

        # Verify data expired
        retrieved_after_ttl = redis_utils.get_registration_data(test_email, test_code)
        if retrieved_after_ttl is not None:
            print_error("Data still exists after TTL expiration")
            return False
        print_success("TTL expiration verified - data automatically deleted")

        return True

    except Exception as e:
        print_error(f"Error testing TTL: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_code_normalization():
    """Test 8: Test code normalization (leading zeros handling)"""
    print_test("Code normalization")

    test_email = "normalize_test@example.com"
    test_code_with_zeros = "012345"
    test_data = {"name": "Normalize Test", "email": test_email, "password": "hashed_password"}

    try:
        # Store with code that has leading zeros
        print_info(f"Storing with code: '{test_code_with_zeros}'")
        stored = redis_utils.store_registration_data(
            email=test_email, code=test_code_with_zeros, registration_data=test_data, ttl_minutes=5
        )
        if not stored:
            print_error("Failed to store registration data")
            return False

        # Try to retrieve with original code
        retrieved1 = redis_utils.get_registration_data(test_email, test_code_with_zeros)
        if not retrieved1:
            print_error("Failed to retrieve with original code")
            return False
        print_success("Retrieved with original code (with leading zeros)")

        # Try to retrieve with normalized code (no leading zeros)
        normalized_code = test_code_with_zeros.lstrip("0") or "0"
        if len(normalized_code) < 6:
            normalized_code = normalized_code.zfill(6)
        retrieved2 = redis_utils.get_registration_data(test_email, normalized_code)
        if retrieved2:
            print_success("Retrieved with normalized code (no leading zeros)")
        else:
            print_warning("Could not retrieve with normalized code (this may be expected)")

        # Cleanup
        redis_utils.delete_registration_data(test_email, test_code_with_zeros)

        return True

    except Exception as e:
        print_error(f"Error testing code normalization: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_error_handling():
    """Test 9: Test error handling"""
    print_test("Error handling")

    try:
        # Test getting non-existent data
        print_info("Testing retrieval of non-existent data...")
        result = redis_utils.get_registration_data("nonexistent@example.com", "000000")
        if result is None:
            print_success("Correctly returned None for non-existent data")
        else:
            print_error("Should return None for non-existent data")
            return False

        # Test deleting non-existent data
        print_info("Testing deletion of non-existent data...")
        deleted = redis_utils.delete_registration_data("nonexistent@example.com", "000000")
        if not deleted:
            print_success("Correctly returned False for non-existent data deletion")
        else:
            print_warning("Deletion returned True for non-existent data (may be acceptable)")

        return True

    except Exception as e:
        print_error(f"Error in error handling test: {e}")
        return False


def cleanup_test_data():
    """Cleanup any remaining test data"""
    print_test("Cleaning up test data")

    test_emails = ["test@example.com", "ttl_test@example.com", "normalize_test@example.com"]

    try:
        client = redis_utils.get_redis_client()
        cleaned = 0

        for email in test_emails:
            pattern = f"registration:{email}:*"
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor, match=pattern, count=100)
                for key in keys:
                    client.delete(key)
                    cleaned += 1
                if cursor == 0:
                    break

            pattern = f"verification:*:{email}:*"
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor, match=pattern, count=100)
                for key in keys:
                    client.delete(key)
                    cleaned += 1
                if cursor == 0:
                    break

        if cleaned > 0:
            print_success(f"Cleaned up {cleaned} test keys")
        else:
            print_info("No test data to clean up")

        return True

    except Exception as e:
        print_warning(f"Could not clean up test data: {e}")
        return True  # Don't fail the test suite for cleanup issues


def main():
    """Run all Redis integration tests"""
    print_header("Redis Server Integration Test Suite")

    results = []

    # Test 1: Library availability
    results.append(("Redis Library", test_redis_library()))

    if not results[-1][1]:
        print_error("\nCannot continue - Redis library is not installed")
        print_info("Install with: pip install redis")
        sys.exit(1)

    # Test 2: Configuration
    results.append(("Redis Configuration", test_redis_configuration()))

    # Test 2.5: DNS Resolution (only if host is configured)
    if settings.REDIS_HOST:
        results.append(("DNS Resolution", test_dns_resolution()))
        dns_ok = results[-1][1]
    else:
        dns_ok = False

    # Test 2.6: Network Connectivity (only if DNS succeeded)
    if dns_ok:
        results.append(("Network Connectivity", test_network_connectivity()))
    else:
        print_warning("Skipping network connectivity test - DNS resolution failed")
        results.append(("Network Connectivity", False))

    # Test 3: Connection
    results.append(("Redis Connection", test_redis_connection()))

    if not results[-1][1]:
        print_error("\nCannot continue - Cannot connect to Redis")
        print_info("Please check your Redis configuration in .env file")
        sys.exit(1)

    # Test 4: Availability check
    results.append(("Redis Availability", test_redis_availability()))

    # Test 5: Registration data operations
    results.append(("Registration Data Operations", test_registration_data_operations()))

    # Test 6: Verification session operations
    results.append(("Verification Session Operations", test_verification_session_operations()))

    # Test 7: TTL functionality
    results.append(("TTL Functionality", test_ttl_functionality()))

    # Test 8: Code normalization
    results.append(("Code Normalization", test_code_normalization()))

    # Test 9: Error handling
    results.append(("Error Handling", test_error_handling()))

    # Cleanup
    cleanup_test_data()

    # Print summary
    print_header("Test Summary")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = (
            f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        )
        print(f"  {status} - {test_name}")

    print(f"\n{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.RESET}\n")

    if passed == total:
        print_success("All tests passed! Redis integration is working correctly.")
        return 0
    else:
        print_error(f"{total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
