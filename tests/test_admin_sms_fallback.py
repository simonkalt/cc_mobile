"""Admin 2FA stays available when Telnyx times out."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from app.api.routers.admin import _deliver_admin_2fa
from app.services.verification_service import SMS_SEND_FAILED_DETAIL
from app.utils.sms_utils import send_sms


class _Response:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}

    def json(self):
        return self._payload


class _Client:
    init_kwargs = []
    posts = []
    script = []

    def __init__(self, *args, **kwargs):
        type(self).init_kwargs.append(kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, headers=None, json=None):
        type(self).posts.append({"url": url, "json": json})
        result = type(self).script.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class TestSendSmsRetries(unittest.TestCase):
    def setUp(self):
        _Client.init_kwargs = []
        _Client.posts = []
        _Client.script = []

    def test_timeout_then_success_uses_ipv4(self):
        _Client.script = [
            httpx.ReadTimeout("read timeout"),
            _Response(200, {"data": {"id": "msg_1"}}),
        ]
        transports = []

        def _transport(**kwargs):
            transports.append(kwargs)
            return object()

        with patch("app.utils.sms_utils.settings") as settings, patch(
            "httpx.Client", _Client
        ), patch("httpx.HTTPTransport", side_effect=_transport):
            settings.TELNYX_API_KEY = "key"
            settings.TELNYX_PHONE_NUMBER = "+15550001111"
            ok = send_sms("+18184195986", "code")

        self.assertTrue(ok)
        self.assertEqual(len(_Client.posts), 2)
        self.assertEqual(
            transports,
            [
                {"local_address": "0.0.0.0", "retries": 0},
                {"local_address": "0.0.0.0", "retries": 0},
            ],
        )
        self.assertTrue(all(kwargs.get("trust_env") is False for kwargs in _Client.init_kwargs))

    def test_two_timeouts_return_false(self):
        _Client.script = [
            httpx.ReadTimeout("read timeout"),
            httpx.ReadTimeout("read timeout"),
        ]
        with patch("app.utils.sms_utils.settings") as settings, patch("httpx.Client", _Client), patch(
            "httpx.HTTPTransport", return_value=object()
        ):
            settings.TELNYX_API_KEY = "key"
            settings.TELNYX_PHONE_NUMBER = "+15550001111"
            ok = send_sms("+18184195986", "code")

        self.assertFalse(ok)
        self.assertEqual(len(_Client.posts), 2)


class TestAdminSmsFallback(unittest.TestCase):
    def test_sms_failure_falls_back_to_email(self):
        user = {"_id": "abc", "email": "admin@example.com", "phone": "+18184195986"}
        with patch(
            "app.api.routers.admin.send_and_store_verification_code",
            side_effect=HTTPException(500, SMS_SEND_FAILED_DETAIL),
        ), patch("app.api.routers.admin.send_and_store_verification_code_email") as email:
            method, message = _deliver_admin_2fa(user, "sms")

        self.assertEqual(method, "email")
        self.assertIn("email", message.lower())
        email.assert_called_once_with(
            user_id="abc",
            email="admin@example.com",
            purpose="admin_2fa",
            delivery_method="email",
        )

    def test_both_channels_fail_is_503(self):
        user = {"_id": "abc", "email": "admin@example.com", "phone": "+18184195986"}
        with patch(
            "app.api.routers.admin.send_and_store_verification_code",
            side_effect=HTTPException(500, SMS_SEND_FAILED_DETAIL),
        ), patch(
            "app.api.routers.admin.send_and_store_verification_code_email",
            side_effect=HTTPException(500, "Failed to send verification code"),
        ):
            with self.assertRaises(HTTPException) as caught:
                _deliver_admin_2fa(user, "sms")

        self.assertEqual(caught.exception.status_code, 503)

    def test_sms_success_does_not_email(self):
        user = {"_id": "abc", "email": "admin@example.com", "phone": "+18184195986"}
        with patch("app.api.routers.admin.send_and_store_verification_code") as sms, patch(
            "app.api.routers.admin.send_and_store_verification_code_email"
        ) as email:
            method, message = _deliver_admin_2fa(user, "sms")

        self.assertEqual(method, "sms")
        self.assertIn("sms", message)
        sms.assert_called_once()
        email.assert_not_called()


if __name__ == "__main__":
    unittest.main()
