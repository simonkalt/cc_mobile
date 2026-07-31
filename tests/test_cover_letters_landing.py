"""Cover-letters marketing routes: redirect, kill-switch, preview override."""

import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient


class TestCoverLettersLanding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import app

        cls.client = TestClient(app, follow_redirects=False)

    def test_root_redirects_to_cover_letters_with_query(self):
        resp = self.client.get("/?utm_source=test")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp.headers.get("location"), "/cover-letters?utm_source=test")

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
