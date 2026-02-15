"""
Cover letter generation API routes
"""

import json
import logging
import os
import re
import html as htmllib
from typing import Any, Dict
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.core.auth import get_current_user
from app.models.user import UserResponse

from app.models.cover_letter import (
    JobInfoRequest,
    ChatRequest,
    CoverLetterWithTextResumeRequest,
    CoverLetterGenerationResponse,
)
from app.services.cover_letter_service import get_job_info
from app.utils.pdf_utils import read_pdf_from_bytes
from app.utils.s3_utils import download_pdf_from_s3, get_s3_client, S3_AVAILABLE
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["cover-letter"],
    dependencies=[Depends(get_current_user)]
)


def _docx_template_hints_from_request(req: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build stable DOCX hints for frontend editors/exporters."""
    return {
        "version": "1.0",
        "sourceFormat": "markdown",
        "outputFormat": "docx",
        "styleProfile": "cover_letter_standard",
        "style": payload.get("docxStyleHints", {}) if isinstance(payload, dict) else {},
        "styleInstructions": getattr(req, "additional_instructions", "") or "",
        "fields": {
            "date_input": getattr(req, "date_input", ""),
            "company_name": getattr(req, "company_name", ""),
            "hiring_manager": getattr(req, "hiring_manager", ""),
            "ad_source": getattr(req, "ad_source", ""),
            "tone": getattr(req, "tone", "Professional"),
            "address": getattr(req, "address", ""),
            "phone_number": getattr(req, "phone_number", ""),
            "additional_instructions": getattr(req, "additional_instructions", ""),
        },
    }


def _sanitize_markdown_no_html(markdown: str) -> str:
    """
    Remove raw HTML tags from markdown content so frontend DOCX creation receives
    plain markdown/text only.
    """
    if not markdown:
        return ""

    text = str(markdown)
    # Preserve common style semantics by converting simple HTML to markdown-like text first.
    for level in range(6, 0, -1):
        text = re.sub(
            rf"<\s*h{level}\b[^>]*>(.*?)<\s*/\s*h{level}\s*>",
            lambda m, n=level: f"{'#' * n} {m.group(1).strip()}\n",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
    text = re.sub(r"<\s*(strong|b)\b[^>]*>(.*?)<\s*/\s*(strong|b)\s*>", r"**\2**", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<\s*(em|i)\b[^>]*>(.*?)<\s*/\s*(em|i)\s*>", r"*\2*", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<\s*li\b[^>]*>", "- ", text, flags=re.IGNORECASE)
    # Convert common block/line-break tags to newlines before stripping remaining tags
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<\s*/\s*(p|div|li|h1|h2|h3|h4|h5|h6)\s*>", "\n", text, flags=re.IGNORECASE)
    # Remove any remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities (&amp;, &nbsp;, etc.)
    text = htmllib.unescape(text)
    # Normalize line endings and whitespace/newline runs
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_generation_response(result: Any, req: Any) -> Dict[str, Any]:
    """
    Enforce DOCX source-of-truth response contract.
    Removes legacy HTML and returns markdown + docxTemplateHints.
    Preserves extra non-HTML metadata fields when present.
    """
    if isinstance(result, dict):
        payload: Dict[str, Any] = dict(result)
    else:
        payload = {"markdown": str(result) if result is not None else ""}

    raw_html = payload.get("html", "") if isinstance(payload, dict) else ""
    payload.pop("docxStyleHints", None)
    payload["markdown"] = _sanitize_markdown_no_html(payload.get("markdown", ""))
    if raw_html:
        payload["html"] = raw_html
    else:
        try:
            import markdown as mdlib

            payload["html"] = mdlib.markdown(
                payload["markdown"],
                extensions=["extra", "nl2br"],
            )
        except Exception:
            payload["html"] = ""
    payload["docxTemplateHints"] = _docx_template_hints_from_request(req, result if isinstance(result, dict) else payload)
    return payload


@router.post("/job-info", response_model=CoverLetterGenerationResponse)
async def handle_job_info(request: JobInfoRequest):
    """
    Generate cover letter based on job information.

    The resume parameter can be:
    - Plain text resume content (pasted by user)
    - S3 key (format: user_id/filename.pdf) - will be downloaded from S3
    - Base64-encoded PDF data - will be decoded and text extracted

    For explicitly pasted resume text, use /api/cover-letter/generate-with-text-resume instead.
    """
    logger.info(
        f"Received job info request for LLM: {request.llm}, Company: {request.company_name}"
    )
    result = get_job_info(
        llm=request.llm,
        date_input=request.date_input,
        company_name=request.company_name,
        hiring_manager=request.hiring_manager,
        ad_source=request.ad_source,
        resume=request.resume,
        jd=request.jd,
        additional_instructions=request.additional_instructions,
        tone=request.tone,
        address=request.address,
        phone_number=request.phone_number,
        user_id=request.user_id,
        user_email=request.user_email,
    )
    return _normalize_generation_response(result, request)


@router.post("/cover-letter/generate-with-text-resume", response_model=CoverLetterGenerationResponse)
async def generate_cover_letter_with_text_resume(request: CoverLetterWithTextResumeRequest):
    """
    Generate cover letter with explicitly pasted resume text.

    This endpoint is designed for cases where the user pastes resume text directly
    instead of uploading a file. The resume_text parameter should contain plain text
    resume content.

    Use this endpoint when:
    - User pastes resume text directly into a text field
    - You want to explicitly indicate that the resume is plain text (not a file path or S3 key)

    For file-based resumes (S3 keys or base64 PDFs), use /api/job-info instead.
    """
    logger.info(
        f"Received cover letter request with text resume for LLM: {request.llm}, Company: {request.company_name}"
    )

    # Pass resume_text directly as resume to get_job_info
    # Set is_plain_text=True to skip file processing (S3, local files, base64)
    result = get_job_info(
        llm=request.llm,
        date_input=request.date_input,
        company_name=request.company_name,
        hiring_manager=request.hiring_manager,
        ad_source=request.ad_source,
        resume=request.resume_text,  # Pass as resume parameter
        jd=request.jd,
        additional_instructions=request.additional_instructions,
        tone=request.tone,
        address=request.address,
        phone_number=request.phone_number,
        user_id=request.user_id,
        user_email=request.user_email,
        is_plain_text=True,  # Skip file processing for pasted text
    )
    return _normalize_generation_response(result, request)


@router.post("/chat")
async def handle_chat(request: Request):
    """Handle both simple chat requests and job info requests"""
    try:
        body = await request.json()

        # Check if resume is an S3 key and needs to be fetched
        resume = body.get("resume")
        user_id = body.get("user_id")

        if resume and S3_AVAILABLE and settings.AWS_S3_BUCKET:
            # Check if resume looks like an S3 key (contains '/' or ends with .pdf)
            is_s3_key = "/" in resume or resume.endswith((".pdf", ".PDF"))

            if is_s3_key and user_id:
                try:
                    # Determine the S3 key
                    # If resume already contains user_id/, use it directly
                    if resume.startswith(f"{user_id}/"):
                        s3_key = resume
                    else:
                        # Check if it's already a full S3 key (starts with another user_id)
                        parts = resume.split("/", 1)
                        if len(parts) == 2 and len(parts[0]) == 24:  # MongoDB ObjectId length
                            # Already has a user_id prefix, use as-is
                            s3_key = resume
                        else:
                            # Extract filename and prepend user_id
                            filename = os.path.basename(resume.replace("\\", "/"))
                            s3_key = f"{user_id}/{filename}"

                    s3_path = f"s3://{settings.AWS_S3_BUCKET}/{s3_key}"
                    logger.info(f"Fetching PDF from S3: {s3_path}")

                    # Download PDF from S3
                    s3_client = get_s3_client()
                    response = s3_client.get_object(Bucket=settings.AWS_S3_BUCKET, Key=s3_key)
                    pdf_bytes = response["Body"].read()

                    # Extract text from PDF
                    resume_text = read_pdf_from_bytes(pdf_bytes)

                    # Replace resume field with extracted text
                    body["resume"] = resume_text

                    # Also update message object if it's being used
                    if "message" in body and body["message"]:
                        try:
                            message_obj = json.loads(body["message"])
                            message_obj["resume"] = resume_text
                            body["message"] = json.dumps(message_obj)
                            logger.info("Updated resume in message object")
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Could not parse message object: {e}")

                    logger.info("Successfully fetched and extracted text from S3 PDF")
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch PDF from S3: {str(e)}. Continuing with original resume value."
                    )

        # Check if this is a job info request
        # Look for job info fields: llm + (company_name OR jd OR resume)
        is_job_info_request = "llm" in body and (
            "company_name" in body or "jd" in body or "resume" in body
        )

        if is_job_info_request:
            logger.info("Detected job info request in /chat endpoint, routing to job-info handler")
            # Check for required user identification
            if not body.get("user_id") and not body.get("user_email"):
                logger.error("Job info request missing user_id or user_email")
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "user_id or user_email is required",
                        "detail": "Please provide either 'user_id' or 'user_email' in your request to access personality profiles.",
                    },
                )
            # Convert to JobInfoRequest and handle it
            try:
                job_request = JobInfoRequest(**body)
            except Exception as e:
                logger.error(f"Invalid job info request: {e}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid job info request",
                        "detail": str(e),
                    },
                )
            result = get_job_info(
                llm=job_request.llm,
                date_input=job_request.date_input,
                company_name=job_request.company_name,
                hiring_manager=job_request.hiring_manager,
                ad_source=job_request.ad_source,
                resume=job_request.resume,
                jd=job_request.jd,
                additional_instructions=job_request.additional_instructions,
                tone=job_request.tone,
                address=job_request.address,
                phone_number=job_request.phone_number,
                user_id=job_request.user_id,
                user_email=job_request.user_email,
            )
            return _normalize_generation_response(result, job_request)
        else:
            # Handle as regular chat request
            chat_request = ChatRequest(**body)
            # TODO: Implement chat functionality or return error
            logger.warning("Chat endpoint not fully implemented in refactored structure")
            return JSONResponse(
                status_code=501, content={"error": "Chat functionality not yet migrated"}
            )
    except Exception as e:
        logger.error(f"Error handling chat request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
