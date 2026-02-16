"""
PDF generation API routes
"""

import asyncio
import base64
import logging
from fastapi import APIRouter, File, HTTPException, UploadFile, status, Depends
from app.core.auth import get_current_user
from app.models.user import UserResponse
from app.models.pdf import GeneratePDFRequest, PrintPreviewPDFRequest, PrintTemplateRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["pdf"], dependencies=[Depends(get_current_user)])

# Lazy-import pdf_service so the router registers even if the service fails to load (e.g. in Docker).
# This avoids 404 on /api/files/print-template when optional deps (playwright, etc.) are missing at import time.


def _get_print_template(print_props_dict, html_content):
    from app.services.pdf_service import get_print_template
    return get_print_template(print_props_dict, html_content)


@router.post("/print-template")
async def print_template_endpoint(request: PrintTemplateRequest):
    """
    Return the exact HTML/CSS wrapper used for PDF generation (single source of truth).

    - **With htmlContent**: Normalizes content (same as PDF pipeline), injects into template,
      returns full document. Use for "Match PDF" or "Print Preview" view—render the returned
      HTML and it will match the PDF.
    - **Without htmlContent**: Returns template with {{LETTER_CONTENT}} placeholder for
      frontend to inject content.

    Use the same printProperties as for POST /api/files/print-preview-pdf.
    """
    ps = request.printProperties.pageSize
    print_props_dict = {
        "margins": {
            "top": request.printProperties.margins.top,
            "right": request.printProperties.margins.right,
            "bottom": request.printProperties.margins.bottom,
            "left": request.printProperties.margins.left,
        },
        "fontFamily": request.printProperties.fontFamily or "Times New Roman",
        "fontSize": request.printProperties.fontSize if request.printProperties.fontSize is not None else 12,
        "lineHeight": request.printProperties.lineHeight if request.printProperties.lineHeight is not None else 1.6,
        "pageSize": {
            "width": ps.width if ps else 8.5,
            "height": ps.height if ps else 11.0,
        },
        "useDefaultFonts": request.printProperties.useDefaultFonts or False,
    }
    result = _get_print_template(print_props_dict, request.htmlContent)
    # Include printProperties in the response so the front-end can apply font size etc.
    # when rendering content in its own container (the same values are already in result["html"] <style>).
    result["printProperties"] = {
        "margins": print_props_dict["margins"],
        "fontFamily": print_props_dict["fontFamily"],
        "fontSize": print_props_dict["fontSize"],
        "lineHeight": print_props_dict["lineHeight"],
        "pageSize": print_props_dict["pageSize"],
        "useDefaultFonts": print_props_dict["useDefaultFonts"],
    }
    if print_props_dict.get("color") is not None:
        result["printProperties"]["color"] = print_props_dict["color"]
    return result


@router.post("/generate-pdf")
async def generate_pdf_endpoint(request: GeneratePDFRequest):
    """
    Generate a PDF from Markdown content with proper formatting support.
    The PDF preserves all Markdown formatting including bold, italic, headings, lists, etc.
    """
    logger.info(
        f"PDF generation request received - user_id: {request.user_id}, user_email: {request.user_email}"
    )

    # Validate required fields
    if not request.markdownContent:
        raise HTTPException(status_code=400, detail="markdownContent is required")

    if not request.printProperties:
        raise HTTPException(status_code=400, detail="printProperties is required")

    if not request.printProperties.margins:
        raise HTTPException(status_code=400, detail="printProperties.margins is required")

    try:
        # Convert Pydantic model to dict for the generation function
        print_props_dict = {
            "margins": {
                "top": request.printProperties.margins.top,
                "right": request.printProperties.margins.right,
                "bottom": request.printProperties.margins.bottom,
                "left": request.printProperties.margins.left,
            },
            "fontFamily": request.printProperties.fontFamily,
            "fontSize": request.printProperties.fontSize,
            "lineHeight": request.printProperties.lineHeight,
            "pageSize": {
                "width": request.printProperties.pageSize.width,
                "height": request.printProperties.pageSize.height,
            },
            "useDefaultFonts": request.printProperties.useDefaultFonts,
        }

        # Generate PDF (lazy import so router registers even if pdf_service fails at import)
        from app.services.pdf_service import generate_pdf_from_markdown
        pdf_base64 = generate_pdf_from_markdown(request.markdownContent, print_props_dict)

        logger.info("PDF generated successfully")
        return {
            "success": True,
            "pdfBase64": pdf_base64,
            "message": "PDF generated successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to generate PDF: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/print-preview-pdf")
async def print_preview_pdf_endpoint(request: PrintPreviewPDFRequest):
    """
    Generate a PDF for Print Preview. HTML is source of truth: send htmlContent.
    markdownContent is accepted for backward compatibility (converted to PDF via markdown pipeline).
    """
    has_html = request.htmlContent and request.htmlContent.strip()
    has_markdown = request.markdownContent and request.markdownContent.strip()
    if not has_html and not has_markdown:
        raise HTTPException(
            status_code=400,
            detail="Either htmlContent or markdownContent is required and cannot be empty",
        )
    if not request.printProperties:
        raise HTTPException(status_code=400, detail="printProperties is required")
    if not request.printProperties.margins:
        raise HTTPException(status_code=400, detail="printProperties.margins is required")

    logger.info(
        "PRINT_PREVIEW_REQUEST - user_id=%s, user_email=%s, source=%s",
        request.user_id,
        request.user_email,
        "html" if has_html else "markdown",
    )
    if request.printProperties and request.printProperties.margins:
        logger.info(
            "Print margins from request (in): top=%s, right=%s, bottom=%s, left=%s",
            request.printProperties.margins.top,
            request.printProperties.margins.right,
            request.printProperties.margins.bottom,
            request.printProperties.margins.left,
        )

    ps = request.printProperties.pageSize
    print_props_dict = {
        "margins": {
            "top": request.printProperties.margins.top,
            "right": request.printProperties.margins.right,
            "bottom": request.printProperties.margins.bottom,
            "left": request.printProperties.margins.left,
        },
        "fontFamily": request.printProperties.fontFamily or "Times New Roman",
        "fontSize": request.printProperties.fontSize if request.printProperties.fontSize is not None else 12,
        "lineHeight": request.printProperties.lineHeight if request.printProperties.lineHeight is not None else 1.6,
        "pageSize": {
            "width": ps.width if ps else 8.5,
            "height": ps.height if ps else 11.0,
        },
        "useDefaultFonts": request.printProperties.useDefaultFonts or False,
    }
    try:
        from app.services.pdf_service import generate_pdf_from_html, generate_pdf_from_markdown
        if has_html:
            pdf_base64 = await generate_pdf_from_html(
                request.htmlContent, print_props_dict, user_id=request.user_id
            )
        else:
            pdf_base64 = generate_pdf_from_markdown(request.markdownContent, print_props_dict)

        logger.info("Print Preview PDF generated successfully")
        return {
            "success": True,
            "pdfBase64": pdf_base64,
            "message": "PDF generated successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to generate Print Preview PDF: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.post("/docx-to-pdf")
async def docx_to_pdf_endpoint(file: UploadFile = File(..., description=".docx file to convert to PDF")):
    """
    Convert a .docx document to PDF (direct conversion; preserves .docx formatting).

    Use this when the cover letter is edited as .docx (e.g. in a Document Editor WebView).
    The PDF is generated from the .docx itself, not from HTML, so formatting matches the document.

    **Requires:** LibreOffice installed on the server (e.g. `soffice` on PATH).
    """
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A .docx file is required. Use the 'file' form field.",
        )

    try:
        docx_bytes = await file.read()
    except Exception as e:
        logger.error("Failed to read uploaded file: %s", e)
        raise HTTPException(status_code=400, detail="Failed to read uploaded file")

    if len(docx_bytes) < 100:
        raise HTTPException(status_code=400, detail="Uploaded file is too small or empty")

    try:
        from app.services.pdf_service import convert_docx_to_pdf
        pdf_bytes = await asyncio.to_thread(convert_docx_to_pdf, docx_bytes)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Docx to PDF is not available: LibreOffice (soffice) is not installed on the server.",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error("Docx to PDF conversion error: %s", e)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    logger.info("Docx to PDF converted successfully (%s bytes PDF)", len(pdf_bytes))
    return {
        "success": True,
        "pdfBase64": pdf_base64,
        "message": "PDF generated from .docx successfully",
    }
