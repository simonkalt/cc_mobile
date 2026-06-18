"""OAuth registration send-verification-code must not crash on helper import."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.services.oauth_registration_service import (
    send_oauth_registration_verification_code,
)


class TestOAuthRegistrationSendCode(unittest.TestCase):
    @patch(
        "app.services.oauth_registration_service.send_and_store_verification_code_email"
    )
    @patch("app.services.oauth_registration_service._load_pending_oauth_user")
    def test_send_code_returns_success(self, mock_load, mock_send):
        mock_load.return_value = {
            "_id": "693326c07fcdaab8e81cdd2f",
            "email": "test@example.com",
            "oauthRegistrationPending": True,
        }
        mock_send.return_value = ("123456", False)

        result = send_oauth_registration_verification_code(
            "693326c07fcdaab8e81cdd2f",
            delivery_method="email",
        )

        self.assertTrue(result["success"])
        self.assertFalse(result["emailDelivered"])
        self.assertIn("emailDeliveryWarning", result)


if __name__ == "__main__":
    unittest.main()
