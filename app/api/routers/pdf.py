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
    Generate a PDF from frontend-modified HTML (Print Preview) using user print preferences.
    Requires printProperties (margins, font, page size, line height). The document is built
    with WeasyPrint using these settings so the PDF matches the user's settings.
    """
    # Use warning so it shows even if log level is WARNING; search for PRINT_PREVIEW_REQUEST
    logger.warning(
        "PRINT_PREVIEW_REQUEST - user_id=%s, user_email=%s, html_content_len=%s",
        request.user_id,
        request.user_email,
        len(request.htmlContent or ""),
    )

    if not request.htmlContent or not request.htmlContent.strip():
        raise HTTPException(status_code=400, detail="htmlContent is required and cannot be empty")
    if not request.printProperties:
        raise HTTPException(status_code=400, detail="printProperties is required")
    if not request.printProperties.margins:
        raise HTTPException(status_code=400, detail="printProperties.margins is required")

    try:
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

        pdf_base64 = await generate_pdf_from_html(request.htmlContent, print_props_dict)

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
