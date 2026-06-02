"""Tests for POST /api/users/me/accept-terms helper."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.services.oauth_registration_service import accept_user_terms


@patch("app.services.oauth_registration_service.user_doc_to_response")
@patch("app.services.oauth_registration_service._users_collection")
def test_accept_user_terms_sets_timestamp(mock_users, mock_to_response):
    user_oid = ObjectId()
    mock_collection = MagicMock()
    mock_users.return_value = mock_collection

    user_doc = {
        "_id": user_oid,
        "email": "user@example.com",
        "isEmailVerified": False,
        "oauthRegistrationPending": False,
    }
    updated_doc = {
        **user_doc,
        "termsOfServiceAcceptedAt": datetime.now(UTC),
        "isEmailVerified": True,
    }
    mock_collection.find_one.side_effect = [user_doc, updated_doc]

    from app.models.user import UserResponse

    now = datetime.now(UTC)
    mock_to_response.return_value = UserResponse(
        id=str(user_oid),
        name="User",
        email="user@example.com",
        isActive=True,
        isEmailVerified=True,
        roles=["user"],
        dateCreated=now,
        dateUpdated=now,
        termsOfServiceAcceptedAt=now,
    )

    result = accept_user_terms(
        str(user_oid),
        terms_of_service_accepted=True,
        provider="apple",
    )

    assert result.isEmailVerified is True
    update_set = mock_collection.update_one.call_args[0][1]["$set"]
    assert "termsOfServiceAcceptedAt" in update_set
    assert update_set.get("isEmailVerified") is True


@patch("app.services.oauth_registration_service._users_collection")
def test_accept_user_terms_requires_flag(mock_users):
    mock_users.return_value = MagicMock()
    with pytest.raises(HTTPException) as exc:
        accept_user_terms("507f1f77bcf86cd799439011", terms_of_service_accepted=False)
    assert exc.value.status_code == 400
