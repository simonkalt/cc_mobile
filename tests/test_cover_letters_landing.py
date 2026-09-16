"""Cover-letters marketing routes and company hub."""

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient


class TestCoverLettersLanding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import app

        cls.client = TestClient(app, follow_redirects=False)

    def test_root_serves_company_hub(self):
        resp = self.client.get("/?utm_source=test")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("sAImon Software", resp.text)
        self.assertIn("globalconcierge", resp.text)
        self.assertIn("Job Cover Letter", resp.text)
        self.assertIn("Marriage Minded", resp.text)
        self.assertIn('href="/cover-letters"', resp.text)
        self.assertIn("https://gc-desk-web.onrender.com/", resp.text)
        self.assertIn('href="/marriage-minded"', resp.text)
        self.assertIn("support@saimonsoft.com", resp.text)
        self.assertIn("+1-702-760-7526", resp.text)
        self.assertIn("Las Vegas", resp.text)
        self.assertNotEqual(resp.headers.get("location"), "/cover-letters?utm_source=test")

    def test_marriage_minded_coming_soon(self):
        resp = self.client.get("/marriage-minded")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Coming soon", resp.text)
        self.assertIn("MM-Logo-A.png", resp.text)
        self.assertIn("Marriage Minded", resp.text)

    def test_marriage_minded_trailing_slash(self):
        resp = self.client.get("/marriage-minded/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Coming soon", resp.text)

    def test_support_host_serves_support(self):
        resp = self.client.get("/", headers={"host": "support.saimonsoft.com"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Support", resp.text)
        self.assertIn("Job Cover Letters", resp.text)
        self.assertNotIn("product-card", resp.text)

    def test_default_serves_legacy(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COVER_LETTERS_LANDING", None)
            resp = self.client.get("/cover-letters")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("X-Landing-Variant"), "legacy")
        self.assertIn("Job Cover Letters", resp.text)
        self.assertIn("data-landing-variant=\"legacy\"", resp.text)
        self.assertIn("play.google.com", resp.text)

    def test_env_v2_serves_conversion_page(self):
        with mock.patch.dict(os.environ, {"COVER_LETTERS_LANDING": "v2"}):
            resp = self.client.get("/cover-letters")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("X-Landing-Variant"), "v2")
        self.assertIn("data-landing-variant=\"v2\"", resp.text)
        self.assertIn("Try for free", resp.text)
        self.assertIn("Your voice", resp.text)
        self.assertIn("Editing_Generated_Letter.png", resp.text)
        self.assertIn("Install required", resp.text)

    def test_query_override_beats_env(self):
        with mock.patch.dict(os.environ, {"COVER_LETTERS_LANDING": "legacy"}):
            resp = self.client.get("/cover-letters?v=v2")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("X-Landing-Variant"), "v2")
        self.assertIn("data-landing-variant=\"v2\"", resp.text)

    def test_trailing_slash_works(self):
        resp = self.client.get("/cover-letters/")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
