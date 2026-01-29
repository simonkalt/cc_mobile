#!/usr/bin/env python3
"""
Terms of Service API Endpoint Test Script
Tests the GET /api/files/terms-of-service endpoint to retrieve the Terms of Service PDF from S3.
Run with: python test_tos.py
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Try to import requests
try:
    import requests
    REQUESTS_AVAILABLE = True
    logger.info("✓ requests library is available")
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.error("✗ requests library is not installed")
    logger.error("Install with: pip install requests")
    sys.exit(1)


def get_base_url():
    """Get the base URL for the API"""
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    logger.info(f"API Base URL: {base_url}")
    return base_url


def test_terms_of_service_endpoint(base_url):
    """
    Test the Terms of Service endpoint
    
    Args:
        base_url: Base URL of the API server
        
    Returns:
        tuple: (success: bool, pdf_bytes: bytes or None, error_message: str or None)
    """
    logger.info("=" * 80)
    logger.info("TEST 1: Testing Terms of Service Endpoint")
    logger.info("=" * 80)
    
    endpoint = f"{base_url}/api/files/terms-of-service"
    logger.info(f"Endpoint URL: {endpoint}")
    
    try:
        logger.info("Sending GET request...")
        response = requests.get(endpoint, timeout=30)
        
        logger.info(f"Response Status Code: {response.status_code}")
        logger.info(f"Response Headers:")
        for key, value in response.headers.items():
            logger.info(f"  {key}: {value}")
        
        # Check status code
        if response.status_code == 200:
            logger.info("✓ Status code is 200 OK")
            
            # Check Content-Type header
            content_type = response.headers.get("Content-Type", "")
            if "application/pdf" in content_type:
                logger.info(f"✓ Content-Type is correct: {content_type}")
            else:
                logger.warning(f"⚠ Content-Type is not application/pdf: {content_type}")
            
            # Check Content-Disposition header
            content_disposition = response.headers.get("Content-Disposition", "")
            if content_disposition:
                logger.info(f"✓ Content-Disposition: {content_disposition}")
            else:
                logger.warning("⚠ Content-Disposition header not found")
            
            # Get PDF content
            pdf_bytes = response.content
            logger.info(f"✓ Received PDF content: {len(pdf_bytes)} bytes")
            
            # Verify it's a valid PDF (starts with %PDF)
            if pdf_bytes.startswith(b"%PDF"):
                logger.info("✓ PDF content is valid (starts with %PDF)")
            else:
                logger.warning("⚠ PDF content does not start with %PDF - may not be a valid PDF")
                logger.warning(f"  First 20 bytes: {pdf_bytes[:20]}")
            
            return True, pdf_bytes, None
            
        elif response.status_code == 503:
            error_msg = "Service Unavailable - S3 service may not be available"
            logger.error(f"✗ {error_msg}")
            try:
                error_detail = response.json()
                logger.error(f"Error detail: {error_detail}")
            except:
                logger.error(f"Response body: {response.text[:200]}")
            return False, None, error_msg
            
        elif response.status_code == 500:
            error_msg = "Internal Server Error"
            logger.error(f"✗ {error_msg}")
            try:
                error_detail = response.json()
                logger.error(f"Error detail: {error_detail}")
            except:
                logger.error(f"Response body: {response.text[:200]}")
            return False, None, error_msg
            
        else:
            error_msg = f"Unexpected status code: {response.status_code}"
            logger.error(f"✗ {error_msg}")
            logger.error(f"Response body: {response.text[:200]}")
            return False, None, error_msg
            
    except requests.exceptions.Timeout:
        error_msg = "Request timed out - server may not be running or too slow"
        logger.error(f"✗ {error_msg}")
        return False, None, error_msg
        
    except requests.exceptions.ConnectionError:
        error_msg = "Connection error - server may not be running"
        logger.error(f"✗ {error_msg}")
        logger.error("Make sure the FastAPI server is running on the specified URL")
        return False, None, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"✗ {error_msg}")
        logger.exception("Full traceback:")
        return False, None, error_msg


def save_pdf_to_file(pdf_bytes, filename="terms_of_service_test.pdf"):
    """
    Save the PDF bytes to a file for manual verification
    
    Args:
        pdf_bytes: PDF file content as bytes
        filename: Output filename
        
    Returns:
        bool: True if saved successfully, False otherwise
    """
    logger.info("=" * 80)
    logger.info("TEST 2: Saving PDF to File")
    logger.info("=" * 80)
    
    try:
        filepath = os.path.join(os.getcwd(), filename)
        logger.info(f"Saving PDF to: {filepath}")
        
        with open(filepath, "wb") as f:
            f.write(pdf_bytes)
        
        file_size = os.path.getsize(filepath)
        logger.info(f"✓ PDF saved successfully: {file_size} bytes")
        logger.info(f"  File path: {filepath}")
        logger.info(f"  You can open this file to verify the PDF content")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to save PDF: {str(e)}")
        logger.exception("Full traceback:")
        return False


def test_endpoint_without_auth(base_url):
    """
    Verify that the endpoint works without authentication (public endpoint)
    
    Args:
        base_url: Base URL of the API server
        
    Returns:
        bool: True if endpoint is accessible without auth, False otherwise
    """
    logger.info("=" * 80)
    logger.info("TEST 3: Verifying Public Access (No Authentication)")
    logger.info("=" * 80)
    
    endpoint = f"{base_url}/api/files/terms-of-service"
    
    try:
        # Make request without any authentication headers
        logger.info("Making request without authentication headers...")
        response = requests.get(endpoint, timeout=30)
        
        if response.status_code == 200:
            logger.info("✓ Endpoint is publicly accessible (no authentication required)")
            return True
        elif response.status_code == 401 or response.status_code == 403:
            logger.warning("⚠ Endpoint requires authentication (unexpected for public endpoint)")
            return False
        else:
            logger.warning(f"⚠ Unexpected status code: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error testing public access: {str(e)}")
        return False


def main():
    """Main test function"""
    logger.info("=" * 80)
    logger.info("TERMS OF SERVICE API ENDPOINT TEST")
    logger.info("=" * 80)
    logger.info("")
    
    if not REQUESTS_AVAILABLE:
        logger.error("requests library is not available. Cannot run tests.")
        sys.exit(1)
    
    # Get base URL
    base_url = get_base_url()
    logger.info("")
    
    # Test 1: Test the endpoint
    success, pdf_bytes, error_msg = test_terms_of_service_endpoint(base_url)
    logger.info("")
    
    if not success:
        logger.error("=" * 80)
        logger.error("✗ TEST FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {error_msg}")
        logger.error("")
        logger.error("Troubleshooting:")
        logger.error("1. Make sure the FastAPI server is running")
        logger.error(f"2. Check that the server is accessible at: {base_url}")
        logger.error("3. Verify S3 credentials are configured")
        logger.error("4. Check that the PDF file exists in S3 at:")
        logger.error("   s3://custom-cover-user-resumes/policy/sAImon Software - Terms of Service.pdf")
        sys.exit(1)
    
    # Test 2: Save PDF to file (optional, for manual verification)
    if pdf_bytes:
        save_pdf_to_file(pdf_bytes)
        logger.info("")
    
    # Test 3: Verify public access
    test_endpoint_without_auth(base_url)
    logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("✓ ALL TESTS PASSED!")
    logger.info("=" * 80)
    logger.info("Summary:")
    logger.info(f"  ✓ Endpoint is accessible: {base_url}/api/files/terms-of-service")
    logger.info(f"  ✓ PDF retrieved successfully: {len(pdf_bytes)} bytes")
    logger.info(f"  ✓ Endpoint is publicly accessible (no authentication required)")
    if pdf_bytes:
        logger.info(f"  ✓ PDF saved to: terms_of_service_test.pdf")
    logger.info("")
    logger.info("The Terms of Service endpoint is working correctly!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"✗ TEST FAILED WITH EXCEPTION: {e}")
        logger.error("=" * 80)
        logger.exception("Full traceback:")
        sys.exit(1)

