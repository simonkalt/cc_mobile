"""Structured OAuth error bodies (FastAPI ``detail`` field)."""

from typing import Any, Dict


def oauth_error_detail(code: str, message: str) -> Dict[str, Any]:
    return {"code": code, "message": message, "detail": message}
