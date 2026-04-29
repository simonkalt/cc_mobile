"""
Load shipped mobile app semver metadata from version.json (see documentation/API_APP_UPDATE_AND_VERSION.md).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_POLICY_STORE_ANDROID = (
    "https://play.google.com/store/apps/details?id=com.saimonsoft.customcoverlettermobile.app"
)


def _coerce_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, str) and val.strip().isdigit():
        return int(val.strip())
    return None


def load_shipped_version(path: Path) -> Dict[str, Any]:
    """
    Read version.json. Returns dict with keys version (str|None), androidVersionCode (int|None),
    buildNumber (str|None). On missing file or parse error, returns null-like structure.
    """
    out: Dict[str, Any] = {
        "version": None,
        "androidVersionCode": None,
        "buildNumber": None,
    }
    if not path or not path.is_file():
        return out
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return out
        ver = data.get("version")
        if ver is None or ver == "":
            out["version"] = None
        else:
            vs = str(ver).strip()
            out["version"] = vs if vs else None
        code = (
            data.get("androidVersionCode")
            if "androidVersionCode" in data
            else data.get("android_version_code")
        )
        out["androidVersionCode"] = _coerce_int(code)
        bn = data.get("buildNumber")
        if bn is None:
            bn = data.get("build_number")
        out["buildNumber"] = str(bn).strip() if bn not in (None, "") else None
    except (OSError, json.JSONDecodeError, TypeError) as e:
        logger.warning("Could not read shipped version.json from %s: %s", path, e)
    return out


def default_play_store_url() -> str:
    return _DEFAULT_POLICY_STORE_ANDROID
