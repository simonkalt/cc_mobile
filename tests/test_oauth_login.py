"""
Unit tests for OAuth login helpers (no live IdP calls).
"""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock, patch

from app.models.oauth import OAuthTokenExchangeRequest
from app.services.oauth_login_service import (
    oauth_link_provider,
    oauth_login,
    oauth_unlink_provider,
)
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


@patch("app.services.oauth_login_service.user_doc_to_response")
@patch("app.services.oauth_login_service._oauth_replace_provider_for_user")
@patch("app.services.oauth_login_service._resolve_identity")
@patch("app.services.oauth_login_service._require_db_collection")
def test_oauth_link_replace_provider(
    mock_db, mock_identity, mock_replace, mock_user_response
):
    from bson import ObjectId

    user_oid = ObjectId()
    mock_collection = MagicMock()
    mock_db.return_value = mock_collection
    mock_identity.return_value = OAuthIdentity(
        provider="google",
        sub="sub-new",
        email="user@example.com",
        email_verified=True,
        name="User",
        picture=None,
    )
    user_doc = {
        "_id": user_oid,
        "email": "user@example.com",
        "authProviders": [{"provider": "google", "subject": "sub-old"}],
    }
    mock_collection.find_one.return_value = user_doc
    mock_replace.return_value = user_doc
    from app.models.user import UserResponse

    now = datetime.now(UTC)
    mock_user_response.return_value = UserResponse(
        id=str(user_oid),
        name="User",
        email="user@example.com",
        isActive=True,
        isEmailVerified=True,
        roles=["user"],
        dateCreated=now,
        dateUpdated=now,
    )

    current_user = mock_user_response.return_value
    body = OAuthTokenExchangeRequest(
        code="code",
        redirect_uri="https://example.com/cb",
        code_verifier="verifier",
        replaceExisting=True,
    )

    result = oauth_link_provider(current_user, "google", body)

    assert result.replacedProvider == "google"
    mock_replace.assert_called_once()


@patch("app.services.oauth_login_service.user_doc_to_response")
@patch("app.services.oauth_login_service._require_db_collection")
def test_oauth_unlink_provider(mock_db, mock_user_response):
    from bson import ObjectId

    from app.models.user import UserResponse

    user_oid = ObjectId()
    mock_collection = MagicMock()
    mock_db.return_value = mock_collection
    user_doc = {
        "_id": user_oid,
        "email": "user@example.com",
        "hashedPassword": "hashed",
        "authProviders": [
            {"provider": "google", "subject": "sub-1"},
            {"provider": "linkedin", "subject": "sub-2"},
        ],
    }
    mock_collection.find_one.side_effect = [user_doc, {**user_doc, "authProviders": [{"provider": "linkedin", "subject": "sub-2"}]}]

    now = datetime.now(UTC)
    mock_user_response.return_value = UserResponse(
        id=str(user_oid),
        name="User",
        email="user@example.com",
        isActive=True,
        isEmailVerified=True,
        roles=["user"],
        dateCreated=now,
        dateUpdated=now,
    )

    current_user = mock_user_response.return_value
    result = oauth_unlink_provider(current_user, "google")

    assert result.unlinkedProvider == "google"
    mock_collection.update_one.assert_called_once()
    pull = mock_collection.update_one.call_args[0][1]["$pull"]
    assert pull == {"authProviders": {"provider": "google"}}


@patch("app.services.oauth_login_service._require_db_collection")
def test_oauth_unlink_last_signin_method(mock_db):
    from bson import ObjectId

    from app.models.user import UserResponse

    user_oid = ObjectId()
    mock_collection = MagicMock()
    mock_db.return_value = mock_collection
    user_doc = {
        "_id": user_oid,
        "email": "oauth@example.com",
        "hashedPassword": "",
        "authProviders": [{"provider": "google", "subject": "sub-1"}],
    }
    mock_collection.find_one.return_value = user_doc

    now = datetime.now(UTC)
    current_user = UserResponse(
        id=str(user_oid),
        name="OAuth",
        email="oauth@example.com",
        isActive=True,
        isEmailVerified=True,
        roles=["user"],
        dateCreated=now,
        dateUpdated=now,
    )

    with pytest.raises(HTTPException) as exc:
        oauth_unlink_provider(current_user, "google")

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "last_signin_method"
