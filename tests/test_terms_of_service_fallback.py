"""Terms of Service endpoint: S3 resolution, fallback, and early router registration."""

import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.utils import terms_of_service as tos


class TestTermsS3UriResolution(unittest.TestCase):
    def test_resolve_uri_uses_aws_s3_bucket_and_key(self):
        with mock.patch.object(tos.settings, "TERMS_OF_SERVICE_S3_URI", None):
            with mock.patch.object(tos.settings, "AWS_S3_BUCKET", "my-bucket"):
                with mock.patch.object(
                    tos.settings,
                    "TERMS_OF_SERVICE_S3_KEY",
                    "policy/sAImon Software - Terms of Service.md",
                ):
                    uri = tos.resolve_terms_markdown_s3_uri()
        self.assertEqual(
            uri,
            "s3://my-bucket/policy/sAImon Software - Terms of Service.md",
        )


class TestTermsPublicRouterWithoutFilesBundle(unittest.TestCase):
    def test_terms_route_without_files_router(self):
        from app.api.routers import terms_public

        app = FastAPI()
        app.include_router(terms_public.router)
        client = TestClient(app)
        with mock.patch.object(
            tos,
            "_load_terms_markdown_from_s3",
            return_value="# Terms\n\nBody",
        ):
            resp = client.get("/api/files/terms-of-service")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Terms", resp.text)


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
