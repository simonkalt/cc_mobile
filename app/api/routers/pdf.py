"""
PDF-related API routes (disabled).

Server-side PDF creation (HTML/Markdown → PDF, print template wrapper, .docx → PDF) has been
moved to the Syncfusion-based .NET service. These routes stay registered so existing clients
receive **HTTP 410 Gone** with a clear message instead of **404**.

Legacy implementation (unused): ``app/services/pdf_service.py`` (retained for reference).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import enforce_integration_auth_if_configured, get_current_user

PDF_DISABLED_DETAIL = (
    "Server-side PDF generation is disabled on this API. "
    "Use the Syncfusion (.NET) service for PDF creation."
)

router = APIRouter(
    prefix="/api/files",
    tags=["pdf"],
    dependencies=[Depends(enforce_integration_auth_if_configured)],
)


@router.post(
    "/print-template",
    dependencies=[Depends(get_current_user)],
    summary="[Disabled] Print HTML template (was PDF wrapper)",
)
async def print_template_endpoint():
    """Previously returned HTML/CSS used for print/PDF. Disabled — use Syncfusion service."""
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=PDF_DISABLED_DETAIL)


@router.post(
    "/generate-pdf",
    dependencies=[Depends(get_current_user)],
    summary="[Disabled] Generate PDF from Markdown",
)
async def generate_pdf_endpoint():
    """Previously generated PDF from Markdown. Disabled — use Syncfusion service."""
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=PDF_DISABLED_DETAIL)


@router.post(
    "/print-preview-pdf",
    dependencies=[Depends(get_current_user)],
    summary="[Disabled] Print preview PDF from HTML/Markdown",
)
async def print_preview_pdf_endpoint():
    """Previously generated print-preview PDF. Disabled — use Syncfusion service."""
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=PDF_DISABLED_DETAIL)


@router.post(
    "/docx-to-pdf",
    summary="[Disabled] Convert .docx to PDF",
)
async def docx_to_pdf_endpoint():
    """Previously converted .docx via LibreOffice. Disabled — use Syncfusion service."""
    raise HTTPException(status_code=status.HTTP_410_GONE, detail=PDF_DISABLED_DETAIL)


# --- Legacy implementation (removed from runtime) ---
# The previous handlers called app.services.pdf_service (get_print_template,
# generate_pdf_from_markdown, generate_pdf_from_html, convert_docx_to_pdf).
# See git history or pdf_service.py for the old code paths.
