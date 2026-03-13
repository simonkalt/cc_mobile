"""
File management API routes
"""
import logging
import base64
import re
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import JSONResponse, Response, HTMLResponse, PlainTextResponse, FileResponse
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
    download_pdf_from_s3,
    S3_AVAILABLE,
)
from app.utils.pdf_utils import read_pdf_from_bytes, read_pdf_markdown_from_bytes
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


@router.get("/profile/bizcard", dependencies=[])
async def get_profile_bizcard():
    """
    Get the public business card PNG from the local website/profile directory.
    """
    import os

    png_filename = "bizcardsk.png"
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    cwd = os.getcwd()
    possible_paths = [
        os.path.join(project_root, "website", "profile", png_filename),
        os.path.join(cwd, "website", "profile", png_filename),
    ]
    for png_path in possible_paths:
        if os.path.exists(png_path):
            return FileResponse(
                png_path,
                media_type="image/png",
                filename=png_filename,
                headers={"Content-Disposition": f'inline; filename="{png_filename}"'},
            )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile business card PNG not found")


@router.get("/profile", dependencies=[])
async def get_profile_pdf():
    """
    Get the public profile resume PDF from the local website/profile directory.
    """
    import os

    pdf_filename = "Simon Kaltgrad Resume 2025 Q3.pdf"
    current_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
    cwd = os.getcwd()
    possible_paths = [
        os.path.join(project_root, "website", "profile", pdf_filename),
        os.path.join(cwd, "website", "profile", pdf_filename),
    ]
    for pdf_path in possible_paths:
        if os.path.exists(pdf_path):
            return FileResponse(
                pdf_path,
                media_type="application/pdf",
                filename=pdf_filename,
                headers={"Content-Disposition": f'inline; filename="{pdf_filename}"'},
            )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile PDF not found")


def _extract_tos_blocks(raw_text: str) -> List[Dict[str, Any]]:
    """
    Convert PDF-extracted Terms text into structural blocks:
    - paragraphs
    - bullet/numbered lists
    """
    text = (raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _reflow_pdf_extracted_text(text)
    lines = text.split("\n")

    blocks: List[Dict[str, Any]] = []
    paragraph_parts: List[str] = []
    list_items: List[str] = []
    list_ordered: Optional[bool] = None

    bullet_re = re.compile(r"^\s*(?:[•\-\*])\s+(.+)$")
    numbered_re = re.compile(r"^\s*(?:\(?[1-9]\d{0,2}\)?[.)])\s+(.+)$")

    def flush_paragraph():
        nonlocal paragraph_parts
        if paragraph_parts:
            blocks.append({"type": "paragraph", "text": " ".join(paragraph_parts).strip()})
            paragraph_parts = []

    def flush_list():
        nonlocal list_items, list_ordered
        if list_items:
            blocks.append({"type": "list", "ordered": bool(list_ordered), "items": list_items[:]})
            list_items = []
            list_ordered = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_list()
            continue

        bullet_match = bullet_re.match(line)
        number_match = numbered_re.match(line)

        if bullet_match or number_match:
            flush_paragraph()
            ordered = bool(number_match)
            item_text = (number_match.group(1) if number_match else bullet_match.group(1)).strip()
            if list_items and list_ordered == ordered:
                list_items.append(item_text)
            else:
                flush_list()
                list_ordered = ordered
                list_items = [item_text]
            continue

        # Continuation line: if we're currently in a list, attach to last item.
        if list_items:
            list_items[-1] = f"{list_items[-1]} {line}".strip()
        else:
            paragraph_parts.append(line)

    flush_paragraph()
    flush_list()
    return blocks


def _reflow_pdf_extracted_text(text: str) -> str:
    """
    Reflow PDF-extracted text that often has hard wraps every visual line.
    Preserves list/headings while joining wrapped prose lines.
    """
    if not text:
        return ""

    bullet_re = re.compile(r"^\s*(?:[•\-\*])\s+")
    numbered_re = re.compile(r"^\s*(?:\(?[1-9]\d{0,2}\)?[.)])\s+")
    heading_re = re.compile(r"^[A-Z][A-Z0-9\s,&\-]{2,}$")

    src_lines = [ln.strip() for ln in text.split("\n")]
    out_parts: List[str] = []
    i = 0

    def is_structural(line: str) -> bool:
        if not line:
            return True
        if bullet_re.match(line) or numbered_re.match(line):
            return True
        if heading_re.match(line) and len(line) <= 80:
            return True
        return False

    while i < len(src_lines):
        line = src_lines[i]
        if not line:
            # keep at most one blank paragraph separator
            if out_parts and out_parts[-1] != "":
                out_parts.append("")
            i += 1
            continue

        if is_structural(line):
            out_parts.append(line)
            i += 1
            continue

        # Build one prose paragraph by consuming continuation lines.
        paragraph = line
        i += 1
        while i < len(src_lines):
            nxt = src_lines[i]
            if not nxt:
                # Skip a single blank if likely just PDF visual wrap spacing.
                if i + 1 < len(src_lines):
                    nxt2 = src_lines[i + 1].strip()
                    if nxt2 and not is_structural(nxt2):
                        paragraph = f"{paragraph} {nxt2}".strip()
                        i += 2
                        continue
                i += 1
                break

            if is_structural(nxt):
                break

            paragraph = f"{paragraph} {nxt}".strip()
            i += 1

        out_parts.append(paragraph)

    # Normalize to single blank lines between blocks.
    result_lines: List[str] = []
    for part in out_parts:
        if part == "":
            if result_lines and result_lines[-1] != "":
                result_lines.append("")
        else:
            result_lines.append(part)
    return "\n".join(result_lines).strip()


def _tos_blocks_to_markdown(blocks: List[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for block in blocks:
        if block.get("type") == "paragraph":
            parts.append(block.get("text", ""))
        elif block.get("type") == "list":
            ordered = bool(block.get("ordered"))
            items = block.get("items", [])
            if ordered:
                for idx, item in enumerate(items, start=1):
                    parts.append(f"{idx}. {item}")
            else:
                for item in items:
                    parts.append(f"- {item}")
        parts.append("")
    return "\n".join(parts).strip()


def _tos_blocks_to_html(blocks: List[Dict[str, Any]]) -> str:
    import html as htmllib

    html_chunks: List[str] = []
    for block in blocks:
        if block.get("type") == "paragraph":
            text = htmllib.escape(block.get("text", ""))
            html_chunks.append(f"<p>{text}</p>")
        elif block.get("type") == "list":
            ordered = bool(block.get("ordered"))
            tag = "ol" if ordered else "ul"
            items = block.get("items", [])
            li_html = "".join(f"<li>{htmllib.escape(item)}</li>" for item in items)
            html_chunks.append(f"<{tag}>{li_html}</{tag}>")
    return "".join(html_chunks)


def _normalize_tos_markdown(text: str) -> str:
    """
    Normalize markdown extracted from PDF so prose reflows naturally
    (avoids narrow-column rendering) while preserving headings/lists.
    """
    src = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not src.strip():
        return ""

    heading_re = re.compile(r"^\s{0,3}#{1,6}\s+")
    bullet_re = re.compile(r"^\s*(?:[-*+]|[•])\s+")
    numbered_re = re.compile(r"^\s*\d+[.)]\s+")

    lines = [ln.strip() for ln in src.split("\n")]
    out: List[str] = []
    para_parts: List[str] = []

    def flush_para():
        nonlocal para_parts
        if para_parts:
            out.append(" ".join(para_parts).strip())
            para_parts = []

    for line in lines:
        if not line:
            flush_para()
            if out and out[-1] != "":
                out.append("")
            continue

        if heading_re.match(line) or bullet_re.match(line) or numbered_re.match(line):
            flush_para()
            out.append(line)
            continue

        para_parts.append(line)

    flush_para()

    # Collapse excessive empty lines.
    normalized: List[str] = []
    for ln in out:
        if ln == "":
            if normalized and normalized[-1] != "":
                normalized.append("")
        else:
            normalized.append(ln)
    return "\n".join(normalized).strip()


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
async def get_terms_of_service(request: Request, format: Optional[str] = None):
    """
    Get the Terms of Service from S3.
    Public endpoint.
    Registration contract default: raw markdown text response body.
    Optional formats are available for manual debugging/inspection.
    """
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    try:
        # Working model: load canonical markdown directly from S3.
        # This avoids lossy PDF -> text conversion artifacts (narrow columns, odd wraps).
        s3_path_md = "s3://custom-cover-user-resumes/policy/sAImon Software - Terms of Service.md"
        path_wo_scheme = s3_path_md[5:] if s3_path_md.startswith("s3://") else s3_path_md
        parts = path_wo_scheme.split("/", 1)
        if len(parts) != 2:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid S3 path format: {s3_path_md}",
            )

        bucket_name, object_key = parts
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        markdown_text = response["Body"].read().decode("utf-8")

        if not markdown_text.strip():
            raise HTTPException(
                status_code=404,
                detail="Terms of Service file not found. Please contact support.",
            )

        requested_format = (format or "").strip().lower()
        if requested_format == "pdf":
            pdf_bytes = download_pdf_from_s3(
                "s3://custom-cover-user-resumes/policy/sAImon Software - Terms of Service.pdf"
            )
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": 'inline; filename=\"Terms of Service.pdf\"'},
            )

        if requested_format in {"", "md", "markdown", "text"}:
            return PlainTextResponse(
                content=markdown_text,
                media_type="text/markdown; charset=utf-8",
            )

        try:
            import markdown as mdlib
            html_content = mdlib.markdown(
                markdown_text, extensions=["extra", "tables", "sane_lists", "nl2br"]
            )
        except Exception:
            import html as htmllib
            html_content = f"<pre>{htmllib.escape(markdown_text)}</pre>"

        return HTMLResponse(
            content=(
                "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
                "<title>Terms of Service</title>"
                "<style>body{font-family:Georgia,serif;max-width:980px;margin:2rem auto;padding:0 1.25rem;line-height:1.55;color:#111;}"
                "h1,h2,h3{margin:1.25rem 0 0.75rem 0;} p{margin:0 0 1rem 0;} ul,ol{margin:0 0 1rem 1.2rem;} li{margin:0.2rem 0;}"
                "</style></head><body>"
                f"{html_content}"
                "</body></html>"
            ),
            media_type="text/html",
        )

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code in {"NoSuchKey", "404"}:
            raise HTTPException(
                status_code=404,
                detail="Terms of Service file not found. Please contact support.",
            )
        if error_code in {"NoCredentialsError", "AccessDenied", "RequestTimeout"}:
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable. Please try again later.",
            )
        raise HTTPException(
            status_code=500,
            detail="Server error. Please try again later or contact support.",
        )
    except Exception as e:
        err = str(e).lower()
        if (
            "credentials" in err
            or "proxy" in err
            or "timed out" in err
            or "connection refused" in err
            or "service unavailable" in err
        ):
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable. Please try again later.",
            )
        raise HTTPException(
            status_code=500,
            detail="Server error. Please try again later or contact support.",
        )

