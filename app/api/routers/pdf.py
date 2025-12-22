"""
PDF generation API routes
"""
import logging
from fastapi import APIRouter, HTTPException, status

from app.models.pdf import GeneratePDFRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["pdf"])

# Import PDF generation service
from app.services.pdf_service import generate_pdf_from_markdown


@router.post("/generate-pdf")
async def generate_pdf_endpoint(request: GeneratePDFRequest):
    """
    Generate a PDF from HTML content with proper formatting support.
    The PDF preserves all formatting including margins, fonts, page size, etc.
    """
    logger.info(
        f"PDF generation request received - htmlContent length: {len(request.htmlContent)}"
    )

    if not request.htmlContent:
        raise HTTPException(status_code=400, detail="htmlContent is required")

    if not request.margins:
        raise HTTPException(status_code=400, detail="margins is required")

    if not request.pageSize:
        raise HTTPException(status_code=400, detail="pageSize is required")

    try:
        # Convert Pydantic model to dict for the generation function
        print_props_dict = {
            "margins": {
                "top": request.margins.top,
                "right": request.margins.right,
                "bottom": request.margins.bottom,
                "left": request.margins.left,
            },
            "fontFamily": request.fontFamily,
            "fontSize": request.fontSize,
            "lineHeight": request.lineHeight,
            "pageSize": {
                "width": request.pageSize.width,
                "height": request.pageSize.height,
            },
            "useDefaultFonts": request.useDefaultFonts,
        }

        # Generate PDF
        pdf_base64 = generate_pdf_from_markdown(
            request.htmlContent, print_props_dict
        )

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

