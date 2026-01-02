"""
File management API routes
"""
import logging
import base64
import re
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse, Response
from botocore.exceptions import ClientError

from app.models.file import (
    FileUploadRequest,
    FileRenameRequest,
    FileDeleteRequest,
)
from app.models.cover_letter import SaveCoverLetterRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])

# Import utilities and services
from app.utils.s3_utils import (
    get_s3_client,
    ensure_user_s3_folder,
    ensure_cover_letter_subfolder,
    S3_AVAILABLE,
)
from app.services.user_service import get_user_by_email
from app.core.config import settings
from app.db.mongodb import is_connected

MONGODB_AVAILABLE = True  # Always available if imported successfully

def get_s3_bucket_name():
    """Get S3 bucket name from settings"""
    bucket_name = settings.AWS_S3_BUCKET
    if not bucket_name:
        # Fallback: try to get from environment variable (for backward compatibility)
        import os
        bucket_name = os.getenv("S3_BUCKET_URI", "").replace("s3://", "").split("/")[0]
    return bucket_name


@router.get("/list")
async def list_files(user_id: Optional[str] = None, user_email: Optional[str] = None):
    """List files from S3 bucket for the authenticated user"""
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    if not user_id and not user_email:
        raise HTTPException(
            status_code=400, detail="user_id or user_email is required to list files"
        )

    # If user_email is provided but not user_id, try to get user_id from email
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
        raise HTTPException(status_code=400, detail="user_id is required to list files")

    try:
        ensure_user_s3_folder(user_id)
        s3_client = get_s3_client()
        bucket_name = get_s3_bucket_name()
        
        if not bucket_name:
            raise HTTPException(status_code=500, detail="S3 bucket name not configured")

        prefix = f"{user_id}/"
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

        files = []
        cover_letters_prefix = f"{user_id}/generated_cover_letters/"
        if "Contents" in response:
            for obj in response["Contents"]:
                if not obj["Key"].endswith("/") and not obj["Key"].endswith(".folder_initialized"):
                    if obj["Key"].startswith(cover_letters_prefix):
                        continue
                    key_after_prefix = obj["Key"][len(prefix):]
                    if "/" in key_after_prefix:
                        continue
                    filename = obj["Key"].replace(prefix, "")
                    files.append({
                        "key": obj["Key"],
                        "name": filename,
                        "size": obj["Size"],
                        "lastModified": obj["LastModified"].isoformat(),
                    })

        files.sort(key=lambda x: x["lastModified"], reverse=True)
        logger.info(f"Listed {len(files)} files for user_id: {user_id}")
        
        # Always return files array, even if empty
        # Frontend should always show the file selection UI (including add button) regardless of file count
        return {"files": files}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Error listing files: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/upload")
async def upload_file(request: FileUploadRequest):
    """Upload a file to S3 bucket on behalf of the user"""
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    if not request.user_id and not request.user_email:
        raise HTTPException(
            status_code=400, detail="user_id or user_email is required to upload files"
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
            status_code=400, detail="user_id is required to upload files"
        )

    ensure_user_s3_folder(user_id)

    try:
        try:
            file_bytes = base64.b64decode(request.fileData)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid base64 fileData: {str(e)}"
            )

        if not request.fileName.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400, detail="Only PDF files are supported"
            )

        if not file_bytes.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400, detail="Invalid PDF file: file does not appear to be a valid PDF"
            )

        s3_key = f"{user_id}/{request.fileName}"
        s3_client = get_s3_client()
        bucket_name = get_s3_bucket_name()
        
        if not bucket_name:
            raise HTTPException(status_code=500, detail="S3 bucket name not configured")
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=file_bytes,
            ContentType=request.contentType,
        )

        logger.info(f"Uploaded file to S3: {s3_key} ({len(file_bytes)} bytes)")
        return {
            "success": True,
            "key": s3_key,
            "fileName": request.fileName,
            "message": "File uploaded successfully",
            "fileSize": len(file_bytes),
        }

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Upload failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.put("/rename")
async def rename_file(request: FileRenameRequest):
    """Rename a file in S3 bucket"""
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
            status_code=400, detail="user_id or user_email is required to rename files"
        )

    try:
        if not request.oldKey.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=403,
                detail="Cannot rename files that don't belong to this user",
            )

        safe_filename = re.sub(r"[^a-zA-Z0-9._\-\s]", "_", request.newFileName)
        safe_filename = safe_filename.strip(". ")

        if not safe_filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        new_key = f"{user_id}/{safe_filename}"

        if new_key == request.oldKey:
            logger.info(f"Filename unchanged: {request.oldKey}")
            return {
                "success": True,
                "key": new_key,
                "fileName": safe_filename,
                "message": "Filename unchanged",
            }

        s3_client = get_s3_client()
        bucket_name = get_s3_bucket_name()
        
        if not bucket_name:
            raise HTTPException(status_code=500, detail="S3 bucket name not configured")
        
        try:
            s3_client.head_object(Bucket=bucket_name, Key=new_key)
            raise HTTPException(
                status_code=409,
                detail=f"A file with the name '{safe_filename}' already exists",
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "404":
                raise

        copy_source = {"Bucket": bucket_name, "Key": request.oldKey}
        s3_client.copy_object(
            CopySource=copy_source, Bucket=bucket_name, Key=new_key
        )
        s3_client.delete_object(Bucket=bucket_name, Key=request.oldKey)

        logger.info(f"Renamed file from {request.oldKey} to {new_key}")
        return {
            "success": True,
            "key": new_key,
            "oldKey": request.oldKey,
            "fileName": safe_filename,
            "message": "File renamed successfully",
        }

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Rename failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.delete("/delete")
async def delete_file_endpoint(request: FileDeleteRequest):
    """Delete a file from S3 bucket"""
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
            status_code=400, detail="user_id or user_email is required to delete files"
        )

    try:
        if not request.key.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=403,
                detail="Cannot delete files that don't belong to this user",
            )

        s3_client = get_s3_client()
        bucket_name = get_s3_bucket_name()
        
        if not bucket_name:
            raise HTTPException(status_code=500, detail="S3 bucket name not configured")
        
        s3_client.delete_object(Bucket=bucket_name, Key=request.key)

        logger.info(f"Deleted file from S3: {request.key}")
        return {"success": True, "message": "File deleted successfully"}

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


@router.post("/save-cover-letter")
async def save_cover_letter(request: SaveCoverLetterRequest):
    """Save a generated cover letter to S3 bucket"""
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
            detail="user_id or user_email is required to save cover letters",
        )

    try:
        ensure_cover_letter_subfolder(user_id)

        import datetime
        if request.fileName:
            safe_filename = re.sub(r"[^a-zA-Z0-9._\-\s]", "_", request.fileName)
            safe_filename = safe_filename.strip(". ")
            if not safe_filename:
                safe_filename = "cover_letter"
        else:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"cover_letter_{timestamp}"

        content_type_lower = request.contentType.lower().strip() if request.contentType else ""

        if content_type_lower == "text/html" or content_type_lower == "html":
            file_extension = ".html"
        elif content_type_lower == "application/pdf" or content_type_lower == "pdf":
            file_extension = ".pdf"
        else:
            file_extension = ".md"

        if safe_filename.endswith((".md", ".html", ".pdf", ".txt")):
            existing_ext = None
            if safe_filename.endswith(".pdf"):
                existing_ext = ".pdf"
            elif safe_filename.endswith(".html"):
                existing_ext = ".html"
            elif safe_filename.endswith(".md"):
                existing_ext = ".md"

            if existing_ext and existing_ext != file_extension:
                base_name = safe_filename.rsplit(".", 1)[0]
                full_filename = f"{base_name}{file_extension}"
            else:
                full_filename = safe_filename
        else:
            full_filename = f"{safe_filename}{file_extension}"

        s3_key = f"{user_id}/generated_cover_letters/{full_filename}"

        if content_type_lower == "application/pdf" or content_type_lower == "pdf":
            try:
                content_bytes = base64.b64decode(request.coverLetterContent)
                if not content_bytes.startswith(b"%PDF"):
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid PDF data: content does not appear to be a valid PDF file",
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid base64 PDF data: {str(e)}"
                )
        else:
            content_bytes = request.coverLetterContent.encode("utf-8")

        if file_extension == ".pdf":
            s3_content_type = "application/pdf"
        elif file_extension == ".html":
            s3_content_type = "text/html"
        else:
            s3_content_type = "text/markdown"

        s3_client = get_s3_client()
        bucket_name = get_s3_bucket_name()
        
        if not bucket_name:
            raise HTTPException(status_code=500, detail="S3 bucket name not configured")
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=content_bytes,
            ContentType=s3_content_type,
        )

        logger.info(f"Saved cover letter to S3: {s3_key} ({len(content_bytes)} bytes)")
        return {
            "success": True,
            "key": s3_key,
            "fileName": full_filename,
            "message": "Cover letter saved successfully",
            "fileSize": len(content_bytes),
        }

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Save cover letter failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/terms-of-service")
async def get_terms_of_service():
    """
    Get the Terms of Service as markdown from S3.
    This is a public endpoint that requires no authentication.
    Returns markdown content that can be displayed or rendered by the client.
    """
    logger.info("Terms of Service endpoint called")
    
    if not S3_AVAILABLE:
        logger.error("S3 not available")
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    try:
        # S3 path to the Terms of Service markdown file
        s3_path = "s3://custom-cover-user-resumes/policy/sAImon Software - Terms of Service.md"
        
        logger.info(f"Attempting to download markdown file from S3: {s3_path}")
        
        # Parse S3 path
        if s3_path.startswith("s3://"):
            s3_path = s3_path[5:]  # Remove 's3://' prefix
        
        # Split bucket and key
        parts = s3_path.split("/", 1)
        if len(parts) != 2:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid S3 path format: {s3_path}"
            )
        
        bucket_name = parts[0]
        object_key = parts[1]
        
        # Download markdown file from S3
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        markdown_content = response["Body"].read().decode('utf-8')
        
        if not markdown_content:
            logger.error("Downloaded markdown file is empty")
            raise HTTPException(
                status_code=404,
                detail="Terms of Service markdown file not found in S3"
            )
        
        logger.info(f"Successfully retrieved Terms of Service markdown ({len(markdown_content)} characters)")
        
        # Return markdown with proper headers
        return Response(
            content=markdown_content.encode('utf-8'),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": 'inline; filename="Terms of Service.md"'
            }
        )
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        if error_code == "NoSuchKey" or error_code == "404":
            raise HTTPException(
                status_code=404,
                detail="Terms of Service markdown file not found in S3"
            )
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Failed to retrieve Terms of Service: {str(e)}"
        logger.error(error_msg, exc_info=True)
        # Check if it's a "not found" type error
        if "NoSuchKey" in str(e) or "404" in str(e) or "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Terms of Service markdown file not found in S3")
        raise HTTPException(status_code=500, detail=error_msg)

