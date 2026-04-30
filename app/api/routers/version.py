"""
Public API: shipped app semver metadata (/api/version). No authentication.
"""
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.app_version_policy_service import build_layer_a_payload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["version"])


class ShippedVersionResponse(BaseModel):
    version: Optional[str] = None
    androidVersionCode: Optional[int] = Field(default=None)
    buildNumber: Optional[str] = None


@router.get("/version", response_model=ShippedVersionResponse)
def get_shipped_app_version():
    """
    Layer A: semver / Android metadata. Primary source: MongoDB policy document;
    optional fallback fields from version.json (VERSION_JSON_PATH).
    """
    data = build_layer_a_payload()
    return ShippedVersionResponse(
        version=data.get("version"),
        androidVersionCode=data.get("androidVersionCode"),
        buildNumber=data.get("buildNumber"),
    )
