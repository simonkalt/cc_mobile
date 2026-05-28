"""
Load project environment: `.env` first, then secrets (overrides).

Local dev: repo-root `.secrets`
Render: secret file uploaded as filename `.secrets` → `/etc/secrets/.secrets`
Override path: set `SECRETS_FILE` to an absolute path.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Render secret-file mount (filename in dashboard must match the basename)
RENDER_SECRETS_PATH = Path("/etc/secrets/.secrets")
LOCAL_SECRETS_NAME = ".secrets"


def resolve_secrets_path(root: Path | str | None = None) -> Path | None:
    """Return the first secrets file that exists, or None."""
    root = Path(root) if root else PROJECT_ROOT

    explicit = (os.getenv("SECRETS_FILE") or "").strip()
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None

    if RENDER_SECRETS_PATH.is_file():
        return RENDER_SECRETS_PATH

    local = root / LOCAL_SECRETS_NAME
    if local.is_file():
        return local

    return None


def load_project_env(root: Path | str | None = None) -> Path:
    """Load `.env` then secrets from *root* (default: repo root)."""
    root = Path(root) if root else PROJECT_ROOT

    env_path = root / ".env"
    if env_path.is_file():
        load_dotenv(env_path)

    secrets_path = resolve_secrets_path(root)
    if secrets_path:
        # On Render, dashboard env vars are set before the process starts; do not let
        # /etc/secrets/.secrets override them (common source of stale ZOHO_* values).
        on_render = bool(
            (os.getenv("RENDER") or "").strip()
            or (os.getenv("RENDER_EXTERNAL_URL") or "").strip()
        )
        load_dotenv(secrets_path, override=not on_render)

    return root
