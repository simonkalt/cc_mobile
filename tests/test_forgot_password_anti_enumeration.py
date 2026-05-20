"""forgot_password send-code must not return 404 for unknown users (anti-enumeration)."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.services.verification_service import ANTI_ENUM_SEND_CODE_MESSAGE


@pytest.fixture
def client():
    from main import app

    with TestClient(app) as tc:
        yield tc


@pytest.fixture
def db_ok():
    with patch("app.api.routers.email.is_connected", return_value=True), patch(
        "app.api.routers.sms.is_connected", return_value=True
    ), patch("app.api.routers.email.get_collection", return_value=MagicMock()), patch(
        "app.api.routers.sms.get_collection", return_value=MagicMock()
    ):
        yield


def test_email_forgot_password_unknown_user_returns_200_generic(client, db_ok):
    with patch(
        "app.api.routers.email.get_user_by_email_ignore_case",
        side_effect=HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found"),
    ), patch(
        "app.api.routers.email.send_and_store_verification_code_email",
    ) as send_mock:
        resp = client.post(
            "/api/email/send-code",
            json={"email": "nobody@example.com", "purpose": "forgot_password"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["message"] == ANTI_ENUM_SEND_CODE_MESSAGE
    send_mock.assert_not_called()


def test_email_change_password_unknown_user_still_404(client, db_ok):
    with patch(
        "app.api.routers.email.get_user_by_email_ignore_case",
        side_effect=HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found"),
    ):
        resp = client.post(
            "/api/email/send-code",
            json={"email": "nobody@example.com", "purpose": "change_password"},
        )

    assert resp.status_code == 404


def test_sms_forgot_password_unknown_email_returns_200_generic(client, db_ok):
    with patch(
        "app.api.routers.sms.get_user_by_email_ignore_case",
        side_effect=HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found"),
    ), patch("app.api.routers.sms.send_and_store_verification_code") as send_mock:
        resp = client.post(
            "/api/sms/send-code",
            json={"email": "nobody@example.com", "purpose": "forgot_password"},
        )

    assert resp.status_code == 200
    assert resp.json()["message"] == ANTI_ENUM_SEND_CODE_MESSAGE
    send_mock.assert_not_called()
