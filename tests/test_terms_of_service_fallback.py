"""Terms of Service endpoint must fall back to bundled markdown when S3 is missing."""

import unittest
from unittest import mock

from fastapi.testclient import TestClient


class TestTermsOfServiceFallback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import app

        cls.client = TestClient(app)

    def test_terms_endpoint_200_with_s3_fallback(self):
        with mock.patch(
            "app.utils.terms_of_service._load_terms_markdown_from_s3",
            return_value=None,
        ):
            resp = self.client.get("/api/files/terms-of-service")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Terms of Service", resp.text)
        self.assertIn("sAImon Software", resp.text)

    def test_load_markdown_from_bundled_file(self):
        from app.utils.terms_of_service import load_terms_of_service_markdown

        with mock.patch(
            "app.utils.terms_of_service._load_terms_markdown_from_s3",
            return_value=None,
        ):
            text = load_terms_of_service_markdown()
        self.assertIn("Terms of Service", text)


if __name__ == "__main__":
    unittest.main()
