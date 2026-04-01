"""
Validate preferences.appSettings.letterTemplateSelection for PUT /api/users/{id}.
"""

import logging
from typing import Any, Dict, Optional, Tuple, Union

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


def apply_letter_template_app_settings_aliases(app_settings: dict) -> None:
    """
    Mutate app_settings: copy snake_case letter prefs to camelCase when camel keys are absent.
    PUT handlers only checked camelCase keys; clients often send snake_case for these two.
    """
    if not isinstance(app_settings, dict):
        return
    if "letterTemplateAutoPick" not in app_settings and "letter_template_auto_pick" in app_settings:
        app_settings["letterTemplateAutoPick"] = app_settings["letter_template_auto_pick"]
    if "letterTemplateSelection" not in app_settings and "letter_template_selection" in app_settings:
        app_settings["letterTemplateSelection"] = app_settings["letter_template_selection"]


def coerce_letter_template_auto_pick_for_update(raw: Any) -> bool:
    """
    JSON often sends booleans as strings or 0/1. Used only when letterTemplateAutoPick is present.
    """
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("true", "1", "yes"):
            return True
        if s in ("false", "0", "no", ""):
            return False
    if isinstance(raw, int) and not isinstance(raw, bool):
        if raw == 1:
            return True
        if raw == 0:
            return False
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="letterTemplateAutoPick must be a boolean (or common JSON equivalents: true/false, \"true\"/\"false\", 1/0).",
    )


def _coerce_selection_name_index_strings(raw: dict) -> Tuple[str, str]:
    """Allow index as int (e.g. JSON number) — strict str-only caused silent 422 and no DB write."""
    name_raw = raw.get("name")
    index_raw = raw.get("index")
    if name_raw is None or index_raw is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="letterTemplateSelection must include name and index.",
        )
    name = str(name_raw).strip()
    if isinstance(index_raw, str):
        index = index_raw.strip()
    elif isinstance(index_raw, bool):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="letterTemplateSelection.index must be a string or number, not a boolean.",
        )
    elif isinstance(index_raw, float):
        if not index_raw.is_integer():
            index = str(index_raw).strip()
        else:
            index = str(int(index_raw))
    elif isinstance(index_raw, int):
        index = str(index_raw)
    else:
        index = str(index_raw).strip()
    if not name or not index:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="letterTemplateSelection.name and letterTemplateSelection.index must be non-empty after trim.",
        )
    return name, index


def log_letter_template_prefs_save_incoming(
    user_id: str, app_settings: Any, *, source: str = "update_user"
) -> None:
    """
    INFO-level troubleshooting: what the client sent for layout prefs on user save.
    """
    if not isinstance(app_settings, dict):
        logger.info(
            "[%s] letter template save [incoming] user_id=%s appSettings not a dict (type=%s)",
            source,
            user_id,
            type(app_settings).__name__,
        )
        return

    def _first(*keys: str) -> Tuple[Optional[str], Any]:
        for k in keys:
            if k in app_settings:
                return k, app_settings[k]
        return None, None

    auto_k, auto_v = _first("letterTemplateAutoPick", "letter_template_auto_pick")
    sel_k, sel_v = _first("letterTemplateSelection", "letter_template_selection")
    related = sorted(
        k
        for k in app_settings.keys()
        if isinstance(k, str) and ("letter" in k.lower() or "template" in k.lower())
    )
    logger.info(
        "[%s] letter template save [incoming] user_id=%s "
        "autoPick: in_body=%s key_used=%s value=%r type=%s | "
        "selection: in_body=%s key_used=%r value=%r type=%s | "
        "appSettings_keys_matching_letter_or_template=%s",
        source,
        user_id,
        auto_k is not None,
        auto_k,
        auto_v,
        type(auto_v).__name__,
        sel_k is not None,
        sel_k,
        sel_v,
        type(sel_v).__name__,
        related,
    )
    if auto_k == "letter_template_auto_pick" or sel_k == "letter_template_selection":
        logger.info(
            "[%s] letter template save: user_id=%s snake_case letter prefs present under appSettings; "
            "server maps them to camelCase before persist.",
            source,
            user_id,
        )


def log_letter_template_prefs_save_skipped_selection_due_to_auto(
    user_id: str, app_settings: dict, *, source: str = "update_user"
) -> None:
    if (
        isinstance(app_settings, dict)
        and "letterTemplateSelection" in app_settings
        and app_settings.get("letterTemplateAutoPick") is True
    ):
        logger.warning(
            "[%s] letter template save: user_id=%s letterTemplateSelection was sent but "
            "letterTemplateAutoPick is True — selection branch skipped (autoPick path cleared selection). raw_selection=%r",
            source,
            user_id,
            app_settings.get("letterTemplateSelection"),
        )


def log_letter_template_prefs_save_update_doc(
    user_id: str, update_doc: dict, *, source: str = "update_user"
) -> None:
    """Log dotted Mongo keys we will $set for letter template prefs (subset of update_doc)."""
    lt = {k: update_doc[k] for k in update_doc if "letterTemplate" in k}
    logger.info(
        "[%s] letter template save [$set] user_id=%s %s",
        source,
        user_id,
        lt if lt else "(no letterTemplate* fields in this update)",
    )


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
    name, index = _coerce_selection_name_index_strings(raw)
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
