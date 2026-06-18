"""Job share import site toggles — validation, defaults, and PATCH endpoint."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from datetime import datetime, timezone

from app.models.user import UserResponse
from app.utils.job_share_import_sites import (
    DEFAULT_JOB_SHARE_IMPORT_SITES,
    normalize_job_share_import_sites,
    validate_job_share_import_sites_patch,
)


class TestJobShareImportSitesUtils(unittest.TestCase):
    def test_normalize_applies_defaults(self):
        self.assertEqual(
            normalize_job_share_import_sites({"indeed": True}),
            {
                **DEFAULT_JOB_SHARE_IMPORT_SITES,
                "indeed": True,
            },
        )

    def test_validate_rejects_unknown_keys(self):
        with self.assertRaises(ValueError) as ctx:
            validate_job_share_import_sites_patch({"linkedin": True, "monster": False})
        self.assertIn("Unknown keys", str(ctx.exception))

    def test_validate_rejects_non_boolean(self):
        with self.assertRaises(ValueError) as ctx:
            validate_job_share_import_sites_patch({"linkedin": "yes"})
        self.assertIn("boolean", str(ctx.exception))


class TestJobShareImportSitesEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import app

        cls.app = app

    def setUp(self):
        self.client = TestClient(self.app)
        self.app.dependency_overrides.clear()

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_client_settings_includes_job_share_import_sites(self):
        with patch(
            "app.api.routers.config.get_job_share_import_sites",
            return_value={"linkedin": True, "indeed": False, "glassdoor": False, "ziprecruiter": False, "generic": False},
        ):
            resp = self.client.get("/api/config/client-settings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("jobShareImportSites", data)
        self.assertTrue(data["jobShareImportSites"]["linkedin"])

    def test_patch_requires_auth(self):
        resp = self.client.patch(
            "/api/config/client-settings/job-share-sites",
            json={"ziprecruiter": True},
        )
        self.assertEqual(resp.status_code, 401)

    def test_patch_forbidden_for_non_super_user(self):
        from app.core.auth import get_current_user

        now = datetime.now(timezone.utc)

        async def _regular_user():
            return UserResponse(
                id="60c72b2f9b1d8b3a2c8e1234",
                name="Regular",
                email="user@example.com",
                isActive=True,
                isEmailVerified=True,
                roles=["user"],
                dateCreated=now,
                dateUpdated=now,
                super_user=False,
            )

        self.app.dependency_overrides[get_current_user] = _regular_user
        resp = self.client.patch(
            "/api/config/client-settings/job-share-sites",
            json={"ziprecruiter": True},
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(resp.status_code, 403)

    def test_patch_merges_and_persists_for_super_user(self):
        from app.core.auth import get_current_user

        now = datetime.now(timezone.utc)

        async def _super_user():
            return UserResponse(
                id="60c72b2f9b1d8b3a2c8e1234",
                name="Super",
                email="super@example.com",
                isActive=True,
                isEmailVerified=True,
                roles=["user"],
                dateCreated=now,
                dateUpdated=now,
                super_user=True,
            )

        self.app.dependency_overrides[get_current_user] = _super_user
        merged = {
            **DEFAULT_JOB_SHARE_IMPORT_SITES,
            "ziprecruiter": True,
        }
        with patch(
            "app.api.routers.config.patch_job_share_import_sites",
            return_value=merged,
        ) as patch_fn:
            resp = self.client.patch(
                "/api/config/client-settings/job-share-sites",
                json={"ziprecruiter": True},
                headers={"Authorization": "Bearer test-token"},
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["jobShareImportSites"]["ziprecruiter"], True)
        patch_fn.assert_called_once_with({"ziprecruiter": True})

    def test_patch_rejects_unknown_keys(self):
        from app.core.auth import get_current_user

        now = datetime.now(timezone.utc)

        async def _super_user():
            return UserResponse(
                id="60c72b2f9b1d8b3a2c8e1234",
                name="Super",
                email="super@example.com",
                isActive=True,
                isEmailVerified=True,
                roles=["user"],
                dateCreated=now,
                dateUpdated=now,
                super_user=True,
            )

        self.app.dependency_overrides[get_current_user] = _super_user
        resp = self.client.patch(
            "/api/config/client-settings/job-share-sites",
            json={"monster": True},
            headers={"Authorization": "Bearer test-token"},
        )
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
