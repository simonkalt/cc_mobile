"""VERIFICATION_EMAIL_FAIL_OPEN defaults for non-production deploys."""

from __future__ import annotations

import importlib
import os
import unittest
from unittest.mock import patch


class TestVerificationEmailFailOpenDefault(unittest.TestCase):
    def _reload_settings(self, env: dict):
        with patch.dict(os.environ, env, clear=False):
            import app.core.config as config_module

            importlib.reload(config_module)
            return config_module.settings

    def test_explicit_false_overrides_uat(self):
        settings = self._reload_settings(
            {
                "VERIFICATION_EMAIL_FAIL_OPEN": "false",
                "RENDER_EXTERNAL_URL": "https://cc-mobile-uat.onrender.com",
            }
        )
        self.assertFalse(settings.VERIFICATION_EMAIL_FAIL_OPEN)

    def test_auto_true_on_render_uat_url(self):
        settings = self._reload_settings(
            {
                "VERIFICATION_EMAIL_FAIL_OPEN": "",
                "RENDER_EXTERNAL_URL": "https://cc-mobile-uat.onrender.com",
            }
        )
        self.assertTrue(settings.VERIFICATION_EMAIL_FAIL_OPEN)


if __name__ == "__main__":
    unittest.main()
