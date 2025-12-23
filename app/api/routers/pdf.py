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
        pdf_base64 = generate_pdf_from_markdown(
            request.markdownContent, print_props_dict
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

