"""
Public API: shipped app semver metadata (/api/version). No authentication.
"""
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings
from app.utils.shipped_app_version import load_shipped_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["version"])


class ShippedVersionResponse(BaseModel):
    version: Optional[str] = None
    androidVersionCode: Optional[int] = Field(default=None)
    buildNumber: Optional[str] = None


@router.get("/version", response_model=ShippedVersionResponse)
def get_shipped_app_version():
    """
    Layer A: semver and Android versionCode from version.json (VERSION_JSON_PATH).
    """
    data = load_shipped_version(settings.VERSION_JSON_PATH)
    return ShippedVersionResponse(
        version=data.get("version"),
        androidVersionCode=data.get("androidVersionCode"),
        buildNumber=data.get("buildNumber"),
    )
