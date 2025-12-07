#!/usr/bin/env python3
"""
S3 Connection Test Script
Tests AWS S3 connectivity, listing, and file upload using the same configuration as the main application.
Run with: python test_s3_connection.py
"""

import os
import sys
import logging
import base64
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Try to import boto3
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
    S3_AVAILABLE = True
    logger.info("✓ boto3 is available")
except ImportError as e:
    S3_AVAILABLE = False
    logger.error(f"✗ boto3 is not installed: {e}")
    logger.error("Install with: pip install boto3")
    sys.exit(1)

def get_environment_variables():
    """Load and validate environment variables"""
    logger.info("=" * 80)
    logger.info("STEP 1: Loading Environment Variables")
    logger.info("=" * 80)
    
    # S3 Bucket URI
    s3_bucket_uri = os.getenv('S3_BUCKET_URI', 's3://custom-cover-user-resumes/')
    logger.info(f"S3_BUCKET_URI: {s3_bucket_uri}")
    
    # Parse bucket name from URI
    if s3_bucket_uri.startswith('s3://'):
        uri_without_prefix = s3_bucket_uri[5:]  # Remove 's3://'
        s3_bucket_name = uri_without_prefix.split('/')[0]
    else:
        s3_bucket_name = s3_bucket_uri.split('/')[0] if '/' in s3_bucket_uri else s3_bucket_uri
    
    logger.info(f"Parsed bucket name: {s3_bucket_name}")
    
    # AWS Credentials
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', '')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    # Log configuration (without exposing secrets)
    logger.info(f"AWS_REGION: {aws_region}")
    logger.info(f"AWS_ACCESS_KEY_ID: {'***SET***' if aws_access_key_id else '***NOT SET***'}")
    logger.info(f"AWS_SECRET_ACCESS_KEY: {'***SET***' if aws_secret_access_key else '***NOT SET***'}")
    
    # Validate required variables
    if not aws_access_key_id:
        logger.warning("⚠ AWS_ACCESS_KEY_ID is not set!")
    if not aws_secret_access_key:
        logger.warning("⚠ AWS_SECRET_ACCESS_KEY is not set!")
    if not s3_bucket_name:
        logger.error("✗ S3 bucket name could not be determined!")
        sys.exit(1)
    
    return {
        'bucket_name': s3_bucket_name,
        'access_key_id': aws_access_key_id,
        'secret_access_key': aws_secret_access_key,
        'region': aws_region
    }

def create_s3_client(config):
    """Create and test S3 client connection"""
    logger.info("=" * 80)
    logger.info("STEP 2: Creating S3 Client")
    logger.info("=" * 80)
    
    try:
        if config['access_key_id'] and config['secret_access_key']:
            logger.info("Creating S3 client with explicit credentials...")
            s3_client = boto3.client(
                's3',
                aws_access_key_id=config['access_key_id'],
                aws_secret_access_key=config['secret_access_key'],
                region_name=config['region']
            )
            logger.info("✓ S3 client created with explicit credentials")
        else:
            logger.info("Creating S3 client with default credentials (IAM role, credentials file, etc.)...")
            s3_client = boto3.client('s3', region_name=config['region'])
            logger.info("✓ S3 client created with default credentials")
        
        # Test connection by getting caller identity (if possible) or listing buckets
        logger.info("Testing S3 connection...")
        try:
            # Try to get account info via STS (if available)
            sts_client = boto3.client('sts', region_name=config['region'])
            if config['access_key_id'] and config['secret_access_key']:
                sts_client = boto3.client(
                    'sts',
                    aws_access_key_id=config['access_key_id'],
                    aws_secret_access_key=config['secret_access_key'],
                    region_name=config['region']
                )
            identity = sts_client.get_caller_identity()
            logger.info(f"✓ AWS Account ID: {identity.get('Account', 'N/A')}")
            logger.info(f"✓ AWS User ARN: {identity.get('Arn', 'N/A')}")
        except Exception as e:
            logger.warning(f"Could not get caller identity: {e}")
            logger.info("Continuing with S3 operations...")
        
        return s3_client
        
    except Exception as e:
        logger.error(f"✗ Failed to create S3 client: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        raise

def test_bucket_access(s3_client, bucket_name):
    """Test if we can access the bucket"""
    logger.info("=" * 80)
    logger.info("STEP 3: Testing Bucket Access")
    logger.info("=" * 80)
    
    try:
        logger.info(f"Checking if bucket '{bucket_name}' exists and is accessible...")
        
        # Try to get bucket location (optional - may not have permission)
        try:
            location = s3_client.get_bucket_location(Bucket=bucket_name)
            logger.info(f"✓ Bucket location: {location.get('LocationConstraint', 'us-east-1')}")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'NoSuchBucket':
                logger.error(f"✗ Bucket '{bucket_name}' does not exist!")
                return False
            elif error_code == 'AccessDenied':
                logger.warning(f"⚠ Cannot get bucket location (AccessDenied) - this is OK, continuing with other tests...")
                logger.warning(f"   Error: {e.response.get('Error', {}).get('Message', 'Unknown error')}")
            else:
                logger.warning(f"Could not get bucket location: {error_code} - {e}")
        
        # Try to head bucket (check if we can access it)
        # Note: This also requires s3:ListBucket permission
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"✓ Bucket '{bucket_name}' is accessible")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'AccessDenied':
                logger.warning(f"⚠ Cannot head bucket (AccessDenied) - trying to list objects instead...")
                logger.warning(f"   This may still work if you have s3:ListBucket permission")
                # Continue anyway - we'll test with list_objects_v2
                return True
            elif error_code == '404':
                logger.error(f"✗ Bucket '{bucket_name}' does not exist (404)")
                return False
            else:
                logger.warning(f"⚠ Cannot head bucket: {error_code} - continuing with other tests...")
                return True
            
    except NoCredentialsError:
        logger.error("✗ AWS credentials not found!")
        logger.error("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error testing bucket access: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        return False

def list_bucket_contents(s3_client, bucket_name, prefix=None):
    """List contents of the bucket"""
    logger.info("=" * 80)
    logger.info("STEP 4: Listing Bucket Contents")
    logger.info("=" * 80)
    
    try:
        list_params = {
            'Bucket': bucket_name,
            'MaxKeys': 100  # Limit to first 100 objects
        }
        
        if prefix:
            list_params['Prefix'] = prefix
            logger.info(f"Listing objects with prefix: '{prefix}'")
        else:
            logger.info("Listing all objects in bucket...")
        
        response = s3_client.list_objects_v2(**list_params)
        
        if 'Contents' in response:
            logger.info(f"✓ Found {len(response['Contents'])} objects")
            for i, obj in enumerate(response['Contents'][:10], 1):  # Show first 10
                logger.info(f"  {i}. Key: {obj['Key']}")
                logger.info(f"     Size: {obj['Size']} bytes")
                logger.info(f"     Modified: {obj['LastModified']}")
            if len(response['Contents']) > 10:
                logger.info(f"  ... and {len(response['Contents']) - 10} more objects")
        else:
            logger.info("✓ Bucket is empty (no objects found)")
        
        return response.get('Contents', [])
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        logger.error(f"✗ Error listing bucket contents: {error_code}")
        logger.error(f"Error: {e}")
        return []
    except Exception as e:
        logger.error(f"✗ Unexpected error listing bucket: {e}")
        return []

def create_test_file():
    """Create a mock PDF file for testing"""
    logger.info("=" * 80)
    logger.info("STEP 5: Creating Test File")
    logger.info("=" * 80)
    
    # Create a simple PDF-like content (minimal valid PDF)
    # This is a minimal PDF that PDF readers will accept
    test_pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 <<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
>>
>>
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test Resume File) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000306 00000 n
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
390
%%EOF"""
    
    logger.info(f"Created test PDF content ({len(test_pdf_content)} bytes)")
    return test_pdf_content

def upload_test_file(s3_client, bucket_name, user_id="test_user_123"):
    """Upload a test file to S3"""
    logger.info("=" * 80)
    logger.info("STEP 6: Uploading Test File")
    logger.info("=" * 80)
    
    try:
        # Create test file content
        file_content = create_test_file()
        
        # Generate unique filename
        timestamp = int(datetime.now().timestamp() * 1000)
        filename = f"test_resume_{timestamp}.pdf"
        s3_key = f"{user_id}/{filename}"
        
        logger.info(f"Uploading to: s3://{bucket_name}/{s3_key}")
        logger.info(f"File size: {len(file_content)} bytes")
        
        # Upload file
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf'
        )
        
        logger.info(f"✓ Successfully uploaded file: {s3_key}")
        
        # Verify upload by checking if object exists
        try:
            response = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
            logger.info(f"✓ Verified file exists in S3")
            logger.info(f"  Content-Type: {response.get('ContentType', 'N/A')}")
            logger.info(f"  Content-Length: {response.get('ContentLength', 'N/A')} bytes")
            logger.info(f"  Last-Modified: {response.get('LastModified', 'N/A')}")
        except Exception as e:
            logger.warning(f"Could not verify uploaded file: {e}")
        
        return s3_key
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        logger.error(f"✗ Error uploading file: {error_code}")
        logger.error(f"Error: {e}")
        logger.error(f"Response: {e.response}")
        return None
    except Exception as e:
        logger.error(f"✗ Unexpected error uploading file: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        return None

def list_user_files(s3_client, bucket_name, user_id="test_user_123"):
    """List files for a specific user"""
    logger.info("=" * 80)
    logger.info("STEP 7: Listing User Files")
    logger.info("=" * 80)
    
    prefix = f"{user_id}/"
    logger.info(f"Listing files for user_id: {user_id}")
    return list_bucket_contents(s3_client, bucket_name, prefix=prefix)

def main():
    """Main test function"""
    logger.info("=" * 80)
    logger.info("S3 CONNECTION TEST SCRIPT")
    logger.info("=" * 80)
    logger.info("")
    
    if not S3_AVAILABLE:
        logger.error("boto3 is not available. Cannot run tests.")
        sys.exit(1)
    
    try:
        # Step 1: Load configuration
        config = get_environment_variables()
        logger.info("")
        
        # Step 2: Create S3 client
        s3_client = create_s3_client(config)
        logger.info("")
        
        # Step 3: Test bucket access
        if not test_bucket_access(s3_client, config['bucket_name']):
            logger.error("Cannot proceed - bucket access failed")
            sys.exit(1)
        logger.info("")
        
        # Step 4: List existing contents
        list_bucket_contents(s3_client, config['bucket_name'])
        logger.info("")
        
        # Step 5 & 6: Create and upload test file
        test_user_id = "test_user_123"
        uploaded_key = upload_test_file(s3_client, config['bucket_name'], user_id=test_user_id)
        logger.info("")
        
        if uploaded_key:
            # Step 7: List user files
            list_user_files(s3_client, config['bucket_name'], user_id=test_user_id)
            logger.info("")
            
            logger.info("=" * 80)
            logger.info("✓ ALL TESTS PASSED!")
            logger.info("=" * 80)
            logger.info(f"Test file uploaded to: s3://{config['bucket_name']}/{uploaded_key}")
        else:
            logger.error("=" * 80)
            logger.error("✗ UPLOAD TEST FAILED")
            logger.error("=" * 80)
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"✗ TEST FAILED WITH EXCEPTION: {e}")
        logger.error("=" * 80)
        logger.exception("Full traceback:")
        sys.exit(1)

if __name__ == "__main__":
    main()

