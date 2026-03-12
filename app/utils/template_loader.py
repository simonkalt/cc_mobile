"""
Cover letter template loading and category selection.

Templates live under templates/{creative,formal,informal}/*.template
Personality profiles are mapped to categories by name.
Multiple templates per category: one is selected at random.
"""

import logging
import random
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Keywords in profile name → template category (case-insensitive)
PROFILE_TO_CATEGORY = {
    "creative": "creative",
    "informal": "informal",
    "casual": "informal",
    "friendly": "informal",
    "formal": "formal",
    "professional": "formal",
}


def get_template_category_from_profile_name(profile_name: str) -> str:
    """
    Map personality profile name to template category.

    Returns one of: "creative", "formal", "informal".
    Default: "formal" if no match.
    """
    if not profile_name or not isinstance(profile_name, str):
        return "formal"
    name_lower = profile_name.lower().strip()
    for keyword, category in PROFILE_TO_CATEGORY.items():
        if keyword in name_lower:
            logger.debug(f"Profile '{profile_name}' → category '{category}'")
            return category
    return "formal"


def load_cover_letter_template(category: str) -> Optional[str]:
    """
    Load a random .template file from templates/{category}/.

    Returns None if category folder missing or empty.
    """
    base = Path(settings.TEMPLATES_DIR)
    if not base.exists():
        logger.warning(f"Templates dir does not exist: {base}")
        return None

    cat_dir = base / category
    if not cat_dir.is_dir():
        logger.warning(f"Template category dir does not exist: {cat_dir}")
        return None

    templates = list(cat_dir.glob("*.template"))
    if not templates:
        logger.warning(f"No .template files in {cat_dir}")
        return None

    chosen = random.choice(templates)
    try:
        content = chosen.read_text(encoding="utf-8")
        logger.info(f"Loaded template: {chosen.relative_to(base)}")
        return content.strip()
    except Exception as e:
        logger.error(f"Failed to read template {chosen}: {e}")
        return None


def get_template_for_profile(profile_name: str) -> Optional[str]:
    """
    Get a cover letter template for the given personality profile name.
    Maps profile → category, then loads a random template from that category.
    Falls back to "formal" if the mapped category has no templates.
    """
    category = get_template_category_from_profile_name(profile_name)
    content = load_cover_letter_template(category)
    if content is None and category != "formal":
        content = load_cover_letter_template("formal")
    return content
