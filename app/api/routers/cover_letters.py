"""
Cover letter management API routes
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from botocore.exceptions import ClientError

from app.models.cover_letter import CoverLetterRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cover-letters", tags=["cover-letters"])

# Import utilities and services
from app.utils.s3_utils import (
    get_s3_client,
    ensure_cover_letter_subfolder,
    S3_AVAILABLE,
)
from app.services.user_service import get_user_by_email
from app.core.config import settings

MONGODB_AVAILABLE = True

def get_s3_bucket_name():
    """Get S3 bucket name from settings"""
    bucket_name = settings.AWS_S3_BUCKET
    if not bucket_name:
        # Fallback: try to get from environment variable (for backward compatibility)
        import os
        bucket_name = os.getenv("S3_BUCKET_URI", "").replace("s3://", "").split("/")[0]
    return bucket_name


@router.get("/list")
async def list_cover_letters(
    user_id: Optional[str] = None, user_email: Optional[str] = None
):
    """List all saved cover letters from the user's generated_cover_letters subfolder"""
    logger.info(
        f"Cover letters list request - user_id: {user_id}, user_email: {user_email}"
    )

    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    if not user_id and not user_email:
        logger.warning("Cover letters list request missing both user_id and user_email")
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to list cover letters",
        )

    if user_email and not user_id:
        logger.info(f"Resolving user_id from email: {user_email}")
        try:
            if MONGODB_AVAILABLE and get_user_by_email:
                user = get_user_by_email(user_email)
                user_id = user.id
                logger.info(
                    f"Successfully resolved user_id: {user_id} from email: {user_email}"
                )
            else:
                logger.error("MongoDB not available, cannot resolve user_id from email")
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404, detail=f"User not found for email: {user_email}"
            )

    if not user_id:
        logger.error("user_id is still None after email resolution attempt")
        raise HTTPException(
            status_code=400, detail="user_id is required to list cover letters"
        )

    logger.info(f"Processing cover letters list request for user_id: {user_id}")

    try:
        ensure_cover_letter_subfolder(user_id)
        s3_client = get_s3_client()
        bucket_name = get_s3_bucket_name()
        
        if not bucket_name:
            raise HTTPException(status_code=500, detail="S3 bucket name not configured")

        prefix = f"{user_id}/generated_cover_letters/"
        logger.info(f"Listing cover letters for user_id: {user_id}, prefix: {prefix}")

        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

        files = []
        if "Contents" in response:
            logger.info(
                f"Found {len(response['Contents'])} objects in S3 for prefix {prefix}"
            )
            for obj in response["Contents"]:
                if not obj["Key"].endswith("/") and not obj["Key"].endswith(".folder_initialized"):
                    filename = obj["Key"].replace(prefix, "")
                    files.append({
                        "key": obj["Key"],
                        "name": filename,
                        "size": obj["Size"],
                        "lastModified": obj["LastModified"].isoformat(),
                    })
        else:
            logger.info(f"No objects found in S3 for prefix {prefix} (empty folder)")

        files.sort(key=lambda x: x["lastModified"], reverse=True)
        logger.info(f"Returning {len(files)} cover letters for user_id: {user_id}")
        return {"files": files}

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Error listing cover letters: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/download")
async def download_cover_letter(
    key: str, user_id: Optional[str] = None, user_email: Optional[str] = None
):
    """Download a cover letter from S3"""
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    if not user_id and not user_email:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to download cover letters",
        )

    if user_email and not user_id:
        try:
            if MONGODB_AVAILABLE and get_user_by_email:
                user = get_user_by_email(user_email)
                user_id = user.id
            else:
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404, detail=f"User not found for email: {user_email}"
            )

    if not user_id:
        raise HTTPException(
            status_code=400, detail="user_id is required to download cover letters"
        )

    if not key.startswith(f"{user_id}/generated_cover_letters/"):
        raise HTTPException(
            status_code=403,
            detail="Cannot download cover letters that don't belong to this user",
        )

    try:
        s3_client = get_s3_client()
        bucket_name = get_s3_bucket_name()
        
        if not bucket_name:
            raise HTTPException(status_code=500, detail="S3 bucket name not configured")
        
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        content = response["Body"].read()
        content_type = response.get("ContentType", "application/octet-stream")

        logger.info(f"Downloaded cover letter from S3: {key} ({len(content)} bytes)")
        return Response(content=content, media_type=content_type)

    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            raise HTTPException(status_code=404, detail="Cover letter not found")
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Download failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.delete("/delete")
async def delete_cover_letter(request: CoverLetterRequest):
    """Delete a cover letter from S3"""
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    user_id = request.user_id
    if request.user_email and not user_id:
        try:
            if MONGODB_AVAILABLE and get_user_by_email:
                user = get_user_by_email(request.user_email)
                user_id = user.id
            else:
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}",
            )

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to delete cover letters",
        )

    if not request.key.startswith(f"{user_id}/generated_cover_letters/"):
        raise HTTPException(
            status_code=403,
            detail="Cannot delete cover letters that don't belong to this user",
        )

    try:
        s3_client = get_s3_client()
        bucket_name = get_s3_bucket_name()
        
        if not bucket_name:
            raise HTTPException(status_code=500, detail="S3 bucket name not configured")
        
        s3_client.delete_object(Bucket=bucket_name, Key=request.key)

        logger.info(f"Deleted cover letter from S3: {request.key}")
        return {"success": True, "message": "Cover letter deleted successfully"}

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Delete failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

