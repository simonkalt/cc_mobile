"""
Cover letter generation API routes
"""

import base64
import datetime
import json
import logging
import os
import re
import html as htmllib
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, status
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
from app.services.user_service import get_user_by_id, get_user_by_email
from app.utils.pdf_utils import read_pdf_from_bytes
from app.utils.s3_utils import download_pdf_from_s3, get_s3_client, S3_AVAILABLE
from app.utils.docx_generator import (
    apply_print_properties_to_docx,
    build_docx_from_components,
    build_docx_from_generation_result,
)
from app.utils.generation_timing import GenerationTiming
from app.core.config import settings

logger = logging.getLogger(__name__)


def _write_client_payload_log(payload: Dict[str, Any]) -> None:
    """
    Write the exact payload sent to the client to tmp/client_payload_sent.txt
    for manual analysis (e.g. to verify line breaks in content). docxBase64 is
    summarized so the file stays readable.
    """
    try:
        _router_dir = os.path.dirname(os.path.abspath(__file__))
        _project_root = os.path.normpath(os.path.join(_router_dir, "..", "..", ".."))
        _tmp_dir = os.path.join(_project_root, "tmp")
        os.makedirs(_tmp_dir, exist_ok=True)
        _path = os.path.join(_tmp_dir, "client_payload_sent.txt")
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = [
            "=" * 80,
            "Payload sent to client (cover letter generation response)",
            f"Timestamp: {ts}",
            "=" * 80,
            "",
        ]
        for key in sorted(payload.keys()):
            val = payload[key]
            if key == "docxBase64" and isinstance(val, str):
                lines.append(f"[{key}] (BASE64, {len(val)} characters)")
                lines.append("")
                continue
            lines.append(f"--- {key} ---")
            if isinstance(val, dict):
                lines.append(json.dumps(val, indent=2, ensure_ascii=False))
            else:
                lines.append(str(val) if val is not None else "")
            lines.append("")
        lines.append("=" * 80)
        with open(_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        logger.info("Wrote client payload to %s for analysis", _path)
    except Exception as e:
        logger.warning("Could not write client payload log: %s", e)


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
    Docx-only contract: preserve "content" (plain text) when present; else legacy markdown/html.
    Always attach docxTemplateHints. Response will expose docxBase64 + docxTemplateHints + optional content.
    """
    if isinstance(result, dict):
        payload: Dict[str, Any] = dict(result)
    else:
        payload = {"content": str(result) if result is not None else ""}

    payload.pop("docxStyleHints", None)
    # When we have docx components (document_xml), keep them for assembly
    if payload.get("document_xml") is not None:
        payload["docxTemplateHints"] = _docx_template_hints_from_request(
            req, result if isinstance(result, dict) else payload
        )
        return payload
    # When we have "content" (docx-only flow), keep it as-is; docx is built from plain text
    if payload.get("content") is not None:
        payload["docxTemplateHints"] = _docx_template_hints_from_request(
            req, result if isinstance(result, dict) else payload
        )
        return payload
    # Legacy: markdown/html
    raw_html = payload.get("html", "")
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
    payload["docxTemplateHints"] = _docx_template_hints_from_request(
        req, result if isinstance(result, dict) else payload
    )
    return payload


def _attach_docx_to_payload(
    payload: Dict[str, Any], req: Any, current_user: Optional[UserResponse] = None
) -> None:
    """
    Build a .docx from docx components (document_xml, numbering_xml, styles_xml),
    or from content (plain text) / legacy markdown/html, and attach as docxBase64.
    """
    try:
        # Resolve print_properties once (request body or user preferences) for both components and content paths
        logger.info("DOCX: determining print_properties for request")
        print_properties = getattr(req, "print_properties", None)
        user = current_user
        if (
            not print_properties
            and user
            and isinstance(getattr(user, "preferences", None), dict)
        ):
            app_settings = (user.preferences or {}).get("appSettings", {})
            if isinstance(app_settings, dict):
                print_properties = app_settings.get("printProperties")
        if not print_properties and not user and getattr(req, "user_id", None):
            try:
                user = get_user_by_id(req.user_id)
                if user and user.preferences:
                    app_settings = (user.preferences or {}).get("appSettings", {})
                    if isinstance(app_settings, dict):
                        print_properties = app_settings.get("printProperties")
            except Exception as e:
                logger.debug("Could not get user print properties by id: %s", e)
        if not print_properties and not user and getattr(req, "user_email", None):
            try:
                user = get_user_by_email(req.user_email)
                if user and user.preferences:
                    app_settings = (user.preferences or {}).get("appSettings", {})
                    if isinstance(app_settings, dict):
                        print_properties = app_settings.get("printProperties")
            except Exception as e:
                logger.debug("Could not get user print properties by email: %s", e)

        # Docx components path: assemble .docx from LLM-returned XML, then apply line height (and font if not default)
        if payload.get("document_xml") is not None:
            logger.info("DOCX: building .docx from components (document_xml, numbering_xml, styles_xml)")
            docx_bytes = build_docx_from_components(
                document_xml=payload["document_xml"],
                numbering_xml=payload.get("numbering_xml"),
                styles_xml=payload.get("styles_xml"),
            )
            docx_bytes = apply_print_properties_to_docx(docx_bytes, print_properties)
            payload["docxBase64"] = base64.b64encode(docx_bytes).decode("utf-8")
            logger.info("Attached .docx from components (%s bytes)", len(docx_bytes))
            return

        # Content/markdown/html path (print_properties already resolved above)
        use_plain_text = "content" in payload
        logger.info("DOCX: building .docx (sync, simplified parser)")
        docx_bytes = build_docx_from_generation_result(
            content=payload.get("content"),
            markdown=payload.get("markdown"),
            html=payload.get("html"),
            print_properties=print_properties,
            use_plain_text=use_plain_text,
        )
        payload["docxBase64"] = base64.b64encode(docx_bytes).decode("utf-8")
        logger.info("Attached .docx to generation response (%s bytes)", len(docx_bytes))
    except ImportError as e:
        logger.warning("python-docx not available, skipping docx generation: %s", e)
    except Exception as e:
        # Critical: do NOT fail the whole request; just log and continue without docx
        logger.error("Failed to build .docx for generation response: %s", e, exc_info=True)


@router.post("/job-info", response_model=CoverLetterGenerationResponse)
async def handle_job_info(
    request: JobInfoRequest, current_user: UserResponse = Depends(get_current_user)
):
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
    timing = GenerationTiming(
        enabled=settings.LOG_TIMING,
        flow_name="cover_letter:/api/job-info",
        client_start_ms=request.client_generate_start_ms,
    )
    timing.checkpoint("request_received")
    try:
        logger.info("Starting get_job_info() for /api/job-info")
        timing.checkpoint("get_job_info_start")
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
            current_user=current_user,
            timing=timing,
            letter_template_name=request.letter_template_name,
            letter_template_index=request.letter_template_index,
            letter_template_auto_pick=request.letter_template_auto_pick,
        )
        timing.checkpoint("get_job_info_done")
        logger.info("get_job_info() completed for /api/job-info")
        payload = _normalize_generation_response(result, request)
        logger.info("Starting DOCX attachment for /api/job-info")
        timing.checkpoint("docx_attach_start")
        _attach_docx_to_payload(payload, request, current_user=current_user)
        timing.checkpoint("docx_attach_done")
        logger.info("DOCX attachment completed for /api/job-info")
        # Docx-only contract: return docx + hints + optional content; no markdown/html
        payload.pop("html", None)
        payload.pop("markdown", None)
        _write_client_payload_log(payload)
        timing.checkpoint("response_ready")
        if settings.LOG_TIMING:
            logger.info("\n%s", timing.chart())
        logger.info("handle_job_info completed, returning payload")
        return payload
    except HTTPException:
        # Already has appropriate status/detail; just log with stack
        logger.error("HTTPException in /api/job-info pipeline", exc_info=True)
        raise
    except Exception as e:
        logger.error("Unexpected error in /api/job-info pipeline: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while generating cover letter",
        )


@router.post("/cover-letter/generate-with-text-resume", response_model=CoverLetterGenerationResponse)
async def generate_cover_letter_with_text_resume(
    request: CoverLetterWithTextResumeRequest,
    current_user: UserResponse = Depends(get_current_user),
):
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
    timing = GenerationTiming(
        enabled=settings.LOG_TIMING,
        flow_name="cover_letter:/api/cover-letter/generate-with-text-resume",
        client_start_ms=request.client_generate_start_ms,
    )
    timing.checkpoint("request_received")

    try:
        logger.info("Starting get_job_info() for /api/cover-letter/generate-with-text-resume")
        timing.checkpoint("get_job_info_start")
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
            current_user=current_user,
            timing=timing,
            letter_template_name=request.letter_template_name,
            letter_template_index=request.letter_template_index,
            letter_template_auto_pick=request.letter_template_auto_pick,
        )
        timing.checkpoint("get_job_info_done")
        logger.info("get_job_info() completed for /api/cover-letter/generate-with-text-resume")
        payload = _normalize_generation_response(result, request)
        logger.info("Starting DOCX attachment for /api/cover-letter/generate-with-text-resume")
        timing.checkpoint("docx_attach_start")
        _attach_docx_to_payload(payload, request, current_user=current_user)
        timing.checkpoint("docx_attach_done")
        logger.info("DOCX attachment completed for /api/cover-letter/generate-with-text-resume")
        payload.pop("html", None)
        payload.pop("markdown", None)
        _write_client_payload_log(payload)
        timing.checkpoint("response_ready")
        if settings.LOG_TIMING:
            logger.info("\n%s", timing.chart())
        logger.info("generate_cover_letter_with_text_resume completed, returning payload")
        return payload
    except HTTPException:
        logger.error(
            "HTTPException in /api/cover-letter/generate-with-text-resume pipeline", exc_info=True
        )
        raise
    except Exception as e:
        logger.error(
            "Unexpected error in /api/cover-letter/generate-with-text-resume pipeline: %s",
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while generating cover letter",
        )


@router.post("/chat")
async def handle_chat(
    request: Request, current_user: UserResponse = Depends(get_current_user)
):
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
            client_start_ms = body.get("client_generate_start_ms")
            timing = GenerationTiming(
                enabled=settings.LOG_TIMING,
                flow_name="cover_letter:/api/chat(job-info)",
                client_start_ms=client_start_ms if isinstance(client_start_ms, int) else None,
            )
            timing.checkpoint("request_received")
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
            timing.checkpoint("get_job_info_start")
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
                current_user=current_user,
                timing=timing,
                letter_template_name=job_request.letter_template_name,
                letter_template_index=job_request.letter_template_index,
                letter_template_auto_pick=job_request.letter_template_auto_pick,
            )
            timing.checkpoint("get_job_info_done")
            payload = _normalize_generation_response(result, job_request)
            timing.checkpoint("docx_attach_start")
            _attach_docx_to_payload(payload, job_request, current_user=current_user)
            timing.checkpoint("docx_attach_done")
            payload.pop("html", None)
            payload.pop("markdown", None)
            _write_client_payload_log(payload)
            timing.checkpoint("response_ready")
            if settings.LOG_TIMING:
                logger.info("\n%s", timing.chart())
            return payload
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
