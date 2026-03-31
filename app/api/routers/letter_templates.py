"""
Cover letter file templates catalog (templates/ on disk).
"""

import logging

from fastapi import APIRouter, HTTPException, status

from app.models.letter_template import LetterTemplatesResponse
from app.services.letter_template_catalog import list_letter_templates_from_disk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/letter-templates", tags=["letter-templates"])


@router.get("", response_model=LetterTemplatesResponse)
async def list_letter_templates():
    """
    List all `.template` files under `templates/{category}/`.

    Each item includes the category display name, full file text (newlines preserved),
    and the file stem as `index` (for future user preference + generation wiring).
    """
    templates = list_letter_templates_from_disk()
    if not templates:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No letter templates available or templates directory is not configured.",
        )
    logger.info("Letter templates catalog: %s file(s)", len(templates))
    return LetterTemplatesResponse(templates=templates)
