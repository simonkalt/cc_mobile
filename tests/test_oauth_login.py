"""
Unit tests for OAuth login helpers (no live IdP calls).
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch

from app.models.oauth import OAuthTokenExchangeRequest
from app.services.oauth_login_service import oauth_login
from app.services.oauth_providers import OAuthIdentity
from app.utils.user_helpers import sanitize_auth_providers_for_response


def test_sanitize_auth_providers_omits_subject():
    linked_at = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    result = sanitize_auth_providers_for_response(
        [
            {
                "provider": "google",
                "subject": "secret-sub-123",
                "linkedAt": linked_at,
                "emailFromProvider": "u@example.com",
            }
        ]
    )
    assert result is not None
    assert len(result) == 1
    assert result[0].provider == "google"
    assert result[0].linkedAt == linked_at
    assert not hasattr(result[0], "subject")


@patch("app.services.oauth_login_service._resolve_identity")
@patch("app.services.oauth_login_service._require_db_collection")
def test_oauth_login_user_not_found(mock_db, mock_identity):
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None
    mock_db.return_value = mock_collection
    mock_identity.return_value = OAuthIdentity(
        provider="google",
        sub="sub-1",
        email="new@example.com",
        email_verified=True,
        name="New User",
        picture=None,
    )

    body = OAuthTokenExchangeRequest(
        code="code",
        redirect_uri="https://example.com/api/auth/oauth/google/callback",
        code_verifier="verifier",
        intent="login",
    )

    with pytest.raises(HTTPException) as exc:
        oauth_login("google", body)

    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "user_not_found"


@patch("app.services.oauth_login_service._resolve_identity")
@patch("app.services.oauth_login_service._require_db_collection")
def test_oauth_login_data_use_notice_required(mock_db, mock_identity):
    mock_collection = MagicMock()
    mock_collection.find_one.return_value = None
    mock_db.return_value = mock_collection
    mock_identity.return_value = OAuthIdentity(
        provider="google",
        sub="sub-2",
        email="brand@example.com",
        email_verified=True,
        name="Brand",
        picture=None,
    )

    body = OAuthTokenExchangeRequest(
        code="code",
        redirect_uri="https://example.com/api/auth/oauth/google/callback",
        code_verifier="verifier",
        intent="register",
        dataUseSharingNoticeAccepted=False,
    )

    with pytest.raises(HTTPException) as exc:
        oauth_login("google", body)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "data_use_notice_required"
