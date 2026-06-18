"""Verification code expiry must tolerate naive datetimes from MongoDB."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from app.services.verification_service import verify_code


class TestVerifyCodeDatetime(unittest.TestCase):
    @patch("app.services.verification_service.get_collection")
    @patch("app.services.verification_service.is_connected", return_value=True)
    def test_verify_accepts_naive_expires_at(self, _connected, mock_get_collection):
        user_id = "6a3460dd1a81e0a166bbc532"
        naive_expires = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=5)
        collection = MagicMock()
        mock_get_collection.return_value = collection
        collection.find_one.return_value = {
            "_id": user_id,
            "verification_code": {
                "code": "123456",
                "purpose": "complete_oauth_registration",
                "expires_at": naive_expires,
            },
        }

        self.assertTrue(
            verify_code(user_id, "123456", "complete_oauth_registration"),
        )


if __name__ == "__main__":
    unittest.main()
