"""
Enumerate cover letter templates from the repo templates/ directory.

Layout: templates/{category}/*.template (e.g. templates/formal/1.template).
"""

import logging
import re
from pathlib import Path
from typing import List

from app.core.config import settings

logger = logging.getLogger(__name__)


def _folder_display_name(folder: str) -> str:
    """Title-style label from a single path segment (e.g. informal -> Informal)."""
    return re.sub(r"[_-]+", " ", folder).strip().title()


def folder_display_name_for_category(folder_name: str) -> str:
    """
    Public alias for catalog display names (must match GET /api/letter-templates `name`).
    """
    return _folder_display_name(folder_name)


def _natural_sort_key(stem: str) -> tuple:
    """Sort stems like 1, 2, 10 numerically when possible."""
    parts = re.split(r"(\d+)", stem)
    key: List = []
    for p in parts:
        if p.isdigit():
            key.append((0, int(p)))
        elif p:
            key.append((1, p.lower()))
    return tuple(key)


def list_letter_templates_from_disk() -> List[dict]:
    """
    Walk settings.TEMPLATES_DIR: one level of category folders, each *.template file.

    Returns list of dicts: name, template, index (strings).
    """
    base = Path(settings.TEMPLATES_DIR)
    if not base.is_dir():
        logger.warning("Templates directory missing or not a directory: %s", base)
        return []

    items: List[dict] = []
    try:
        category_dirs = sorted(
            p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
    except OSError as e:
        logger.error("Cannot read templates directory %s: %s", base, e)
        return []

    for cat_dir in category_dirs:
        display_name = _folder_display_name(cat_dir.name)
        try:
            files = sorted(
                cat_dir.glob("*.template"),
                key=lambda p: _natural_sort_key(p.stem),
            )
        except OSError as e:
            logger.warning("Cannot list %s: %s", cat_dir, e)
            continue

        for path in files:
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as e:
                logger.warning("Cannot read template %s: %s", path, e)
                continue
            items.append(
                {
                    "name": display_name,
                    "template": text,
                    "index": path.stem,
                }
            )

    return items
