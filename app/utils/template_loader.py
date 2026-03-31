"""
Cover letter template loading and selection.

Templates live under templates/{category}/*.template (e.g. formal/1.template).
- When the user saved a catalog selection (and did not explicitly leave AI pick on),
  that file is used (same keys as GET /api/letter-templates).
- Otherwise the personality profile name maps to a category and one file is chosen at random.
"""

import logging
import random
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import settings
from app.services.letter_template_catalog import folder_display_name_for_category

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


def load_cover_letter_template_by_name_and_index(
    display_name: str, index: str
) -> Optional[str]:
    """
    Load templates/{category}/{index}.template where category's display label matches
    GET /api/letter-templates `name` (e.g. Formal, Informal).
    """
    base = Path(settings.TEMPLATES_DIR)
    if not base.exists() or not base.is_dir():
        logger.warning("Templates dir missing or not a directory: %s", base)
        return None
    dn = display_name.strip()
    ix = index.strip()
    if not dn or not ix:
        return None
    try:
        category_dirs = sorted(
            p for p in base.iterdir() if p.is_dir() and not p.name.startswith(".")
        )
    except OSError as e:
        logger.warning("Cannot list templates dir %s: %s", base, e)
        return None
    for cat_dir in category_dirs:
        if folder_display_name_for_category(cat_dir.name) != dn:
            continue
        path = cat_dir / f"{ix}.template"
        if not path.is_file():
            logger.debug("No file %s for selection name=%r index=%r", path, dn, ix)
            return None
        try:
            content = path.read_text(encoding="utf-8").strip()
            logger.info("Loaded user-selected template %s", path.relative_to(base))
            return content
        except OSError as e:
            logger.error("Failed to read template %s: %s", path, e)
            return None
    logger.debug("No category folder matches display name %r", dn)
    return None


def coalesce_letter_template_app_settings(
    app_settings: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Normalize Mongo/client keys so camelCase and snake_case both work."""
    app = dict(app_settings) if isinstance(app_settings, dict) else {}
    if "letterTemplateAutoPick" not in app and "letter_template_auto_pick" in app:
        app["letterTemplateAutoPick"] = app.get("letter_template_auto_pick")
    if "letterTemplateSelection" not in app and "letter_template_selection" in app:
        app["letterTemplateSelection"] = app.get("letter_template_selection")
    return app


def merge_request_letter_template_prefs(
    app_settings: Dict[str, Any],
    *,
    letter_template_name: Optional[str] = None,
    letter_template_index: Optional[Any] = None,
    letter_template_auto_pick: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Per-generate overrides from the API body. When name+index are sent, that file wins
    for this request even if DB prefs are stale or still on AI pick.
    """
    out = dict(app_settings) if isinstance(app_settings, dict) else {}
    nm = (letter_template_name or "").strip()
    ix_raw = letter_template_index
    if ix_raw is not None and nm:
        if isinstance(ix_raw, str):
            ix = ix_raw.strip()
        elif isinstance(ix_raw, float) and not ix_raw.is_integer():
            ix = str(ix_raw).strip()
        elif isinstance(ix_raw, (int, float)):
            ix = str(int(ix_raw))
        else:
            ix = str(ix_raw).strip()
        if ix:
            out["letterTemplateSelection"] = {"name": nm, "index": ix}
            out["letterTemplateAutoPick"] = False
    if letter_template_auto_pick is not None:
        out["letterTemplateAutoPick"] = bool(letter_template_auto_pick)
        if letter_template_auto_pick is True:
            out["letterTemplateSelection"] = None
    return out


def _coerce_letter_template_auto_pick(raw: Any) -> Optional[bool]:
    """None = missing key. True/False = explicit."""
    if raw is None:
        return None
    if raw is True or raw is False:
        return bool(raw)
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s == "true":
            return True
        if s in ("false", "0", "no"):
            return False
    return None


def template_selection_name_index(sel: Any) -> Optional[tuple[str, str]]:
    """Normalized (name, index) for disk lookup; index may have been stored as a number."""
    if not isinstance(sel, dict):
        return None
    raw_name, raw_idx = sel.get("name"), sel.get("index")
    if raw_name is None or raw_idx is None:
        return None
    name = str(raw_name).strip()
    if isinstance(raw_idx, str):
        idx = raw_idx.strip()
    elif isinstance(raw_idx, (int, float)):
        if isinstance(raw_idx, float) and not raw_idx.is_integer():
            idx = str(raw_idx).strip()
        else:
            idx = str(int(raw_idx))
    else:
        idx = str(raw_idx).strip()
    if not name or not idx:
        return None
    return (name, idx)


def manual_letter_template_selection_active(app_settings: Optional[Dict[str, Any]]) -> bool:
    """
    True when we should load the user's chosen catalog file (not random-by-profile).

    - letterTemplateAutoPick explicitly True => AI/random (ignore stale selection in DB).
    - letterTemplateAutoPick explicitly False with valid selection => manual.
    - Key missing/None but valid selection => manual (clients that only persist selection).
    """
    app_settings = coalesce_letter_template_app_settings(app_settings)
    auto = _coerce_letter_template_auto_pick(app_settings.get("letterTemplateAutoPick"))
    pair = template_selection_name_index(app_settings.get("letterTemplateSelection"))
    if auto is True:
        return False
    if pair is None:
        return False
    if auto is False:
        return True
    # Missing or unrecognized auto key — use saved selection if present
    return True


def use_file_template_in_prompt(
    app_settings: Optional[Dict[str, Any]], use_template_setting: bool
) -> bool:
    """
    Inject file template into the LLM prompt when USE_TEMPLATE_IN_PROMPT is on,
    or when the user picked a specific template (always honor that choice).
    """
    if use_template_setting:
        return True
    return manual_letter_template_selection_active(app_settings)


def letter_template_cache_stamp(app_settings: Optional[Dict[str, Any]]) -> str:
    """Fragment for generation result cache keys."""
    app_settings = coalesce_letter_template_app_settings(app_settings)
    if manual_letter_template_selection_active(app_settings):
        pair = template_selection_name_index(
            (app_settings or {}).get("letterTemplateSelection")
        )
        if pair:
            return f"manual:{pair[0]}:{pair[1]}"
        return "manual_invalid"
    return "auto"


def resolve_cover_letter_template_for_generation(
    *,
    profile_name: str,
    app_settings: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    User-chosen file when manual selection is active; else profile → category → random.
    """
    app_settings = coalesce_letter_template_app_settings(app_settings)
    if manual_letter_template_selection_active(app_settings):
        pair = template_selection_name_index(
            app_settings.get("letterTemplateSelection")
        )
        if pair:
            name_f, idx_f = pair
            content = load_cover_letter_template_by_name_and_index(name_f, idx_f)
            if content:
                return content
            logger.warning(
                "letterTemplateSelection name=%r index=%r not on disk; "
                "falling back to profile-based template",
                name_f,
                idx_f,
            )
    return get_template_for_profile(profile_name)
