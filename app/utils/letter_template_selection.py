"""
Validate preferences.appSettings.letterTemplateSelection for PUT /api/users/{id}.
"""

import logging
from typing import Any, Dict, Optional, Union

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def normalize_letter_template_selection_for_storage(
    raw: Any,
) -> Union[None, Dict[str, str]]:
    """
    Returns None to clear the field, or {"name": str, "index": str}.
    Raises HTTPException 422 if malformed.

    When the on-disk template catalog is non-empty, enforces that the pair exists
    in GET /api/letter-templates data.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="letterTemplateSelection must be an object with string name and index, or null.",
        )
    name = raw.get("name")
    index = raw.get("index")
    if not isinstance(name, str) or not isinstance(index, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="letterTemplateSelection.name and letterTemplateSelection.index must be strings.",
        )
    name = name.strip()
    index = index.strip()
    if not name or not index:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="letterTemplateSelection.name and letterTemplateSelection.index must be non-empty after trim.",
        )
    try:
        from app.services.letter_template_catalog import list_letter_templates_from_disk

        catalog = list_letter_templates_from_disk()
    except Exception as exc:
        logger.warning("Letter template catalog unavailable for validation: %s", exc)
        catalog = []
    if catalog:
        found = any(
            item.get("name") == name and item.get("index") == index for item in catalog
        )
        if not found:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"No template matches name={name!r} and index={index!r}. "
                    "Use values from GET /api/letter-templates."
                ),
            )
    return {"name": name, "index": index}
