"""Job share import site toggles (share-to-app rollout)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional

JOB_SHARE_SITE_IDS = (
    "linkedin",
    "indeed",
    "glassdoor",
    "ziprecruiter",
    "generic",
)

DEFAULT_JOB_SHARE_IMPORT_SITES: Dict[str, bool] = {
    "linkedin": True,
    "indeed": False,
    "glassdoor": False,
    "ziprecruiter": False,
    "generic": False,
}


def normalize_job_share_import_sites(
    raw: Optional[Mapping[str, Any]],
) -> Dict[str, bool]:
    """Merge partial server/client input with defaults."""
    out = dict(DEFAULT_JOB_SHARE_IMPORT_SITES)
    if not raw or not isinstance(raw, Mapping):
        return out
    for site_id in JOB_SHARE_SITE_IDS:
        value = raw.get(site_id)
        if isinstance(value, bool):
            out[site_id] = value
    return out


def validate_job_share_import_sites_patch(
    partial: Mapping[str, Any],
) -> Dict[str, bool]:
    """
    Validate PATCH body keys/values.

    Raises:
        ValueError: with a message suitable for HTTP 400 detail.
    """
    if not isinstance(partial, Mapping):
        raise ValueError("Request body must be a JSON object")
    unknown = [k for k in partial.keys() if k not in JOB_SHARE_SITE_IDS]
    if unknown:
        allowed = ", ".join(JOB_SHARE_SITE_IDS)
        raise ValueError(
            f"Unknown keys: {', '.join(unknown)}. Allowed keys: {allowed}"
        )
    invalid = [
        k
        for k, v in partial.items()
        if k in JOB_SHARE_SITE_IDS and not isinstance(v, bool)
    ]
    if invalid:
        raise ValueError(
            f"Values must be boolean for keys: {', '.join(invalid)}"
        )
    return {k: partial[k] for k in partial.keys() if k in JOB_SHARE_SITE_IDS}
