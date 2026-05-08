"""
Mobile app update policy — implementation in this repo:

- `app/services/app_version_policy_service.py` — MongoDB (primary), env overrides, version.json fallback
- `GET /api/version` — `app/api/routers/version.py`
- `GET /api/config/app-update-policy` — `app/api/routers/config.py` (`get_app_update_policy`)
- Collection access — `app/db/mongodb.py` (`get_app_update_policy_collection`)

Environment variables: see documentation/API_APP_UPDATE_AND_VERSION.md
(`APP_UPDATE_POLICY_*`, `VERSION_JSON_PATH`, `APP_UPDATE_*` overrides).

Canonical document: database **`CoverLetter`**, collection **`version`** (defaults in `app/core/config.py`; override with `APP_UPDATE_POLICY_*`).
Resolve the document via `APP_UPDATE_POLICY_DOC_ID`, `APP_UPDATE_POLICY_DOC_FILTER_JSON`, or
heuristic queries on `version` / `min_required_version` fields.
"""
