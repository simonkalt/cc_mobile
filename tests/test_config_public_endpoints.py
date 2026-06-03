"""Public config endpoints must register and return 200 (client-settings, app-update-policy)."""

import unittest

from fastapi.testclient import TestClient


class TestConfigPublicEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import app

        cls.client = TestClient(app)

    def test_client_settings_returns_expected_keys(self):
        resp = self.client.get("/api/config/client-settings")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("enforceStrongPasswords", data)
        self.assertIn("passwordPolicy", data)
        self.assertIn("privacyPolicyUrl", data)
        self.assertIn("termsOfServiceUrl", data)
        self.assertIn("registrationDataUseNotice", data)
        policy = data["passwordPolicy"]
        self.assertEqual(policy["minLength"], 8)
        self.assertTrue(policy["requireUppercase"])

    def test_app_update_policy_returns_semver_fields(self):
        resp = self.client.get("/api/config/app-update-policy")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("min_required_version", data)
        self.assertIn("latest_version", data)
        self.assertIn("store_android_url", data)
        self.assertTrue(data["min_required_version"])
        self.assertTrue(data["latest_version"])
        self.assertIn(
            "com.saimonsoft.customcoverlettermobile.app",
            data["store_android_url"],
        )

    def test_shipped_version_endpoint(self):
        resp = self.client.get("/api/version")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("version", data)


if __name__ == "__main__":
    unittest.main()
