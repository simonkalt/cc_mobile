"""
AWS S3 utilities for file management
"""
import logging
import os
from typing import Optional
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import boto3
try:
    import boto3
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logger.warning("boto3 not available. S3 operations will not work.")


def get_s3_client():
    """
    Get S3 client with proper credentials
    
    Returns:
        boto3 S3 client instance
        
    Raises:
        ImportError: If boto3 is not installed
    """
    if not S3_AVAILABLE:
        raise ImportError("boto3 is not installed. Cannot access S3.")

    # Create S3 client with credentials if provided, otherwise use default
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        logger.info("Using AWS credentials from environment variables")
        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
    else:
        logger.info(
            "Using default AWS credentials (IAM role, credentials file, or environment)"
        )
        return boto3.client("s3", region_name=settings.AWS_REGION)


def download_pdf_from_s3(s3_path: str, bucket_name: Optional[str] = None) -> bytes:
    """
    Download PDF from S3 bucket and return as bytes
    
    Args:
        s3_path: S3 path in format s3://bucket/key or bucket/key
        bucket_name: Optional bucket name (if not in s3_path)
        
    Returns:
        PDF file content as bytes
        
    Raises:
        Exception: If download fails
    """
    if not S3_AVAILABLE:
        raise ImportError("boto3 is not installed. Cannot download from S3.")

    try:
        # Parse S3 path
        if s3_path.startswith("s3://"):
            s3_path = s3_path[5:]  # Remove 's3://' prefix

        # Split bucket and key
        parts = s3_path.split("/", 1)
        if len(parts) == 2:
            parsed_bucket = parts[0]
            object_key = parts[1]
        elif bucket_name:
            parsed_bucket = bucket_name
            object_key = s3_path
        else:
            raise ValueError(
                f"Invalid S3 path format: {s3_path}. Expected format: bucket/key or s3://bucket/key"
            )

        bucket_name = parsed_bucket or settings.AWS_S3_BUCKET
        if not bucket_name:
            raise ValueError("Bucket name is required")

        logger.info(f"Downloading PDF from S3: bucket={bucket_name}, key={object_key}")

        # Get S3 client
        s3_client = get_s3_client()

        # Download the object
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        pdf_bytes = response["Body"].read()

        logger.info(f"Successfully downloaded PDF from S3 ({len(pdf_bytes)} bytes)")
        return pdf_bytes

    except NoCredentialsError:
        error_msg = (
            "AWS credentials not found. Cannot download from S3. "
            "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables, "
            "or configure AWS credentials file, or use an IAM role."
        )
        logger.error(error_msg)
        raise Exception(error_msg)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"Error downloading from S3: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error downloading from S3: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def ensure_user_s3_folder(user_id: str, bucket_name: Optional[str] = None) -> bool:
    """
    Ensure a user's S3 folder exists. If it doesn't exist, create it.
    In S3, folders are just prefixes, so we create a placeholder object.
    
    Args:
        user_id: User ID
        bucket_name: Optional bucket name (defaults to configured bucket)
        
    Returns:
        True if folder exists or was created successfully, False otherwise
    """
    if not S3_AVAILABLE:
        logger.warning("S3 is not available. Cannot ensure user folder.")
        return False

    bucket_name = bucket_name or settings.AWS_S3_BUCKET
    if not bucket_name:
        logger.warning("S3 bucket name not configured. Cannot ensure user folder.")
        return False

    if not user_id:
        logger.warning("user_id is required to ensure S3 folder.")
        return False

    try:
        s3_client = get_s3_client()
        folder_prefix = f"{user_id}/"
        placeholder_key = f"{user_id}/.folder_initialized"

        # Check if folder exists by trying to list objects with the prefix
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name, Prefix=folder_prefix, MaxKeys=1
            )

            # If we get any objects (even the placeholder), folder exists
            if "Contents" in response and len(response["Contents"]) > 0:
                logger.info(f"User S3 folder already exists: {folder_prefix}")
                return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "AccessDenied":
                logger.warning(f"Cannot check if folder exists (AccessDenied): {e}")
                # Continue to try creating it anyway
            else:
                logger.warning(f"Error checking folder existence: {error_code}")

        # Folder doesn't exist or we can't check, create placeholder
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=placeholder_key,
                Body=b"",
                ContentType="text/plain",
            )
            logger.info(f"Created user S3 folder: {folder_prefix}")
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Failed to create user S3 folder: {error_code} - {e}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error ensuring user S3 folder: {e}")
        return False


def ensure_cover_letter_subfolder(user_id: str, bucket_name: Optional[str] = None) -> bool:
    """
    Ensure a user's generated_cover_letters subfolder exists.
    
    Args:
        user_id: User ID
        bucket_name: Optional bucket name (defaults to configured bucket)
        
    Returns:
        True if subfolder exists or was created successfully, False otherwise
    """
    if not S3_AVAILABLE:
        logger.warning("S3 is not available. Cannot ensure cover letter subfolder.")
        return False

    bucket_name = bucket_name or settings.AWS_S3_BUCKET
    if not bucket_name:
        logger.warning("S3 bucket name not configured. Cannot ensure cover letter subfolder.")
        return False

    if not user_id:
        logger.warning("user_id is required to ensure cover letter subfolder.")
        return False

    try:
        # First ensure the main user folder exists
        ensure_user_s3_folder(user_id, bucket_name)

        s3_client = get_s3_client()
        subfolder_prefix = f"{user_id}/generated_cover_letters/"
        placeholder_key = f"{user_id}/generated_cover_letters/.folder_initialized"

        # Check if subfolder exists
        try:
            response = s3_client.list_objects_v2(
                Bucket=bucket_name, Prefix=subfolder_prefix, MaxKeys=1
            )

            if "Contents" in response and len(response["Contents"]) > 0:
                logger.info(f"Cover letter subfolder already exists: {subfolder_prefix}")
                return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "AccessDenied":
                logger.warning(f"Cannot check if subfolder exists (AccessDenied): {e}")
            else:
                logger.warning(f"Error checking subfolder existence: {error_code}")

        # Subfolder doesn't exist, create placeholder
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=placeholder_key,
                Body=b"",
                ContentType="text/plain",
            )
            logger.info(f"Created cover letter subfolder: {subfolder_prefix}")
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Failed to create cover letter subfolder: {error_code} - {e}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error ensuring cover letter subfolder: {e}")
        return False

