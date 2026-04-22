"""
Load the Data Use & Sharing Notice from JSON and validate registration consent.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings

logger = logging.getLogger(__name__)

_FALLBACK_NOTICE: Dict[str, Any] = {
    "noticeTypographicStyle": "italic",
    "noticeText": (
        "<p>By creating an account, you acknowledge and consent to the following:</p>"
        "<ul style='list-style:disc outside;margin:0.65em 0 0.85em 0;padding-left:1.5em;'>"
        "<li style='margin-bottom:0.45em;'>Your phone number is shared with Tenlyx to deliver SMS messages "
        "you opt in to receive.</li>"
        "<li style='margin-bottom:0.45em;'>Your email address is processed via Zoho Mail for account and "
        "support communications.</li>"
        "<li style='margin-bottom:0.45em;'>When you use AI-powered features, your input is sent to "
        "third-party AI services including Anthropic (Claude), OpenAI (ChatGPT), Google (Gemini), and "
        "X Corp. (Grok) to generate responses. These providers do not use your data for advertising.</li>"
        "<li style='margin-bottom:0.45em;'>Your account data is stored securely using Amazon Web Services "
        "(AWS), MongoDB Atlas, and Redis.</li></ul>"
        "<p style='margin-top:0.65em;'>We do not sell your personal data. You may withdraw consent and "
        "request deletion of your data at any time by visiting Settings &gt; Delete My Account or emailing "
        "<a href='mailto:support@saimonsoft.com'>support@saimonsoft.com</a>.</p>"
        "<p style='margin-top:0.45em;'>For full details, see our Privacy Policy.</p>"
    ),
    "checkboxLabel": (
        "I have read and agree to the Data Use & Sharing Notice above, including the sharing of my data "
        "with third-party AI services and service providers."
    ),
    "checkboxLeadingSymbol": "☐",
    "checkboxLabelWithSymbol": (
        "☐  I have read and agree to the Data Use & Sharing Notice above, including the sharing of my data "
        "with third-party AI services and service providers."
    ),
}


def load_registration_data_use_notice() -> Dict[str, Any]:
    """Return notice copy for client-settings; falls back to built-in text if the JSON file is missing."""
    path: Path = settings.REGISTRATION_DATA_USE_NOTICE_PATH
    try:
        if not path.is_file():
            logger.warning("Registration notice JSON not found at %s; using fallback.", path)
            return dict(_FALLBACK_NOTICE)
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.error("Registration notice JSON must be an object; using fallback.")
            return dict(_FALLBACK_NOTICE)
        merged = dict(_FALLBACK_NOTICE)
        merged.update(data)
        return merged
    except Exception as e:
        logger.error("Failed to load registration notice from %s: %s", path, e, exc_info=True)
        return dict(_FALLBACK_NOTICE)


def registration_data_includes_notice_acceptance(registration_data: Dict[str, Any]) -> bool:
    if not isinstance(registration_data, dict):
        return False
    if registration_data.get("data_use_sharing_notice_accepted") is True:
        return True
    if registration_data.get("dataUseSharingNoticeAccepted") is True:
        return True
    return False


def assert_data_use_sharing_notice_accepted(registration_data: Dict[str, Any]) -> None:
    from fastapi import HTTPException, status

    if registration_data_includes_notice_acceptance(registration_data):
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="You must accept the Data Use & Sharing Notice to register.",
    )
