"""
Reference: app update policy + shipped version endpoints.

Production implementation lives in this repo:
  - GET /api/version              -> app/api/routers/version.py
  - GET /api/config/app-update-policy -> app/api/routers/config.py (get_app_update_policy)
  - version.json loading          -> app/utils/shipped_app_version.py
  - settings / env vars           -> app/core/config.py (VERSION_JSON_PATH, APP_UPDATE_*)

Environment variables (see documentation/API_APP_UPDATE_AND_VERSION.md):
  VERSION_JSON_PATH, APP_UPDATE_MIN_REQUIRED_VERSION, APP_UPDATE_LATEST_VERSION,
  APP_UPDATE_MESSAGE, APP_UPDATE_STORE_ANDROID_URL, APP_UPDATE_STORE_IOS_URL
"""
