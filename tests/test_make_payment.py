"""Unlisted /make-payment marketing page."""

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient


class TestMakePaymentPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import app

        cls.client = TestClient(app, follow_redirects=False)

    def test_serves_page_with_defaults(self):
        resp = self.client.get("/make-payment")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Make a payment to sAImon Software", resp.text)
        self.assertIn("specify what the payment is for", resp.text)
        self.assertIn("paypal.com/sdk/js", resp.text)
        self.assertIn("client-id=", resp.text)
        self.assertIn("hosted-buttons", resp.text)
        self.assertIn("enable-funding=venmo", resp.text)
        self.assertIn("currency=USD", resp.text)
        self.assertIn("2GMS84Y7YGKJ4", resp.text)
        self.assertIn("paypal.HostedButtons", resp.text)
        self.assertIn('name="robots" content="noindex, nofollow"', resp.text)
        self.assertEqual(resp.headers.get("X-Robots-Tag"), "noindex, nofollow")

    def test_trailing_slash_works(self):
        resp = self.client.get("/make-payment/")
        self.assertEqual(resp.status_code, 200)

    def test_env_overrides_paypal_ids(self):
        with mock.patch.dict(
            os.environ,
            {
                "PAYPAL_CLIENT_ID": "TESTCLIENTID123",
                "PAYPAL_HOSTED_BUTTON_ID": "HOSTEDBTN99",
                "PAYPAL_CURRENCY": "CAD",
                "PAYPAL_ENABLE_FUNDING": "venmo,paypal",
            },
        ):
            resp = self.client.get("/make-payment")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("TESTCLIENTID123", resp.text)
        self.assertIn("HOSTEDBTN99", resp.text)
        self.assertIn("paypal-container-HOSTEDBTN99", resp.text)
        self.assertIn("currency=CAD", resp.text)
        self.assertIn("enable-funding=venmo%2Cpaypal", resp.text)

    def test_not_linked_from_marketing_pages(self):
        for path in ("/cover-letters", "/support.html", "/delete-account.html", "/news"):
            resp = self.client.get(path)
            self.assertEqual(resp.status_code, 200, path)
            self.assertNotIn("/make-payment", resp.text)
            self.assertNotIn("Make a Payment", resp.text)


if __name__ == "__main__":
    unittest.main()
