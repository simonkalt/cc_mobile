"""
PDF generation API routes
"""

import logging
from fastapi import APIRouter, HTTPException, status, Depends
from app.core.auth import get_current_user
from app.models.user import UserResponse
from app.models.pdf import GeneratePDFRequest, PrintPreviewPDFRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["pdf"], dependencies=[Depends(get_current_user)])

# Import PDF generation service
from app.services.pdf_service import generate_pdf_from_markdown, generate_pdf_from_html


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

        # Generate PDF
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
    Generate a PDF from frontend-modified HTML (Print Preview).
    Send your styled HTML; the API wraps it in a minimal document with optional
    page options and returns the PDF as base64.
    """
    logger.info(
        "Print Preview PDF request received - user_id=%s, user_email=%s",
        request.user_id,
        request.user_email,
    )

    if not request.htmlContent or not request.htmlContent.strip():
        raise HTTPException(status_code=400, detail="htmlContent is required and cannot be empty")

    try:
        page_options = None
        if request.pageOptions:
            page_options = {}
            if request.pageOptions.margins:
                page_options["margins"] = {
                    "top": request.pageOptions.margins.top,
                    "right": request.pageOptions.margins.right,
                    "bottom": request.pageOptions.margins.bottom,
                    "left": request.pageOptions.margins.left,
                }
            if request.pageOptions.pageSize:
                page_options["pageSize"] = {
                    "width": request.pageOptions.pageSize.width,
                    "height": request.pageOptions.pageSize.height,
                }

        pdf_base64 = generate_pdf_from_html(request.htmlContent, page_options)

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
