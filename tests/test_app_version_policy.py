"""Tests for app version policy payload merge (Mongo + file + env)."""

import unittest
from unittest import mock

from app.services import app_version_policy_service as avp


class TestAppVersionPolicyPayload(unittest.TestCase):
    def test_layer_b_from_mongo_only(self):
        doc = {
            "version": "2.3.0",
            "min_required_version": "2.1.0",
            "update_message": "Please update",
            "store_android_url": "https://play.example/custom",
        }
        with mock.patch.object(avp, "get_cached_policy_document", return_value=doc):
            with mock.patch.object(
                avp,
                "load_shipped_version",
                return_value={
                    "version": None,
                    "androidVersionCode": None,
                    "buildNumber": None,
                },
            ):
                with mock.patch.object(avp.settings, "APP_UPDATE_MIN_REQUIRED_VERSION", None):
                    with mock.patch.object(avp.settings, "APP_UPDATE_LATEST_VERSION", None):
                        with mock.patch.object(avp.settings, "APP_UPDATE_MESSAGE", None):
                            with mock.patch.object(
                                avp.settings, "APP_UPDATE_STORE_ANDROID_URL", None
                            ):
                                with mock.patch.object(
                                    avp.settings, "APP_UPDATE_STORE_IOS_URL", None
                                ):
                                    with mock.patch.object(avp.settings, "APP_VERSION", "9.9.9"):
                                        p = avp.build_layer_b_payload()
        self.assertEqual(p["min_required_version"], "2.1.0")
        self.assertEqual(p["latest_version"], "2.3.0")
        self.assertEqual(p["update_message"], "Please update")
        self.assertEqual(p["store_android_url"], "https://play.example/custom")
        self.assertIsNone(p["store_ios_url"])

    def test_env_overrides_mongo(self):
        doc = {"version": "2.0.0", "min_required_version": "1.0.0"}
        with mock.patch.object(avp, "get_cached_policy_document", return_value=doc):
            with mock.patch.object(
                avp,
                "load_shipped_version",
                return_value={
                    "version": None,
                    "androidVersionCode": None,
                    "buildNumber": None,
                },
            ):
                with mock.patch.object(
                    avp.settings, "APP_UPDATE_MIN_REQUIRED_VERSION", "3.0.0"
                ):
                    with mock.patch.object(
                        avp.settings, "APP_UPDATE_LATEST_VERSION", "3.1.0"
                    ):
                        with mock.patch.object(avp.settings, "APP_UPDATE_MESSAGE", None):
                            with mock.patch.object(
                                avp.settings, "APP_UPDATE_STORE_ANDROID_URL", None
                            ):
                                with mock.patch.object(
                                    avp.settings, "APP_UPDATE_STORE_IOS_URL", None
                                ):
                                    p = avp.build_layer_b_payload()
        self.assertEqual(p["min_required_version"], "3.0.0")
        self.assertEqual(p["latest_version"], "3.1.0")

    def test_layer_a_prefers_mongo_version(self):
        doc = {
            "version": "2.5.0",
            "android_version_code": 2500,
            "build_number": "b1",
        }
        with mock.patch.object(avp, "get_cached_policy_document", return_value=doc):
            with mock.patch.object(
                avp,
                "load_shipped_version",
                return_value={
                    "version": "1.0.0",
                    "androidVersionCode": 100,
                    "buildNumber": "x",
                },
            ):
                with mock.patch.object(avp.settings, "APP_VERSION", "0.0.1"):
                    p = avp.build_layer_a_payload()
        self.assertEqual(p["version"], "2.5.0")
        self.assertEqual(p["androidVersionCode"], 2500)
        self.assertEqual(p["buildNumber"], "b1")

    def test_min_defaults_zero_when_missing(self):
        with mock.patch.object(avp, "get_cached_policy_document", return_value=None):
            with mock.patch.object(
                avp,
                "load_shipped_version",
                return_value={
                    "version": "1.2.0",
                    "androidVersionCode": None,
                    "buildNumber": None,
                },
            ):
                with mock.patch.object(avp.settings, "APP_UPDATE_MIN_REQUIRED_VERSION", None):
                    with mock.patch.object(avp.settings, "APP_UPDATE_LATEST_VERSION", None):
                        with mock.patch.object(avp.settings, "APP_UPDATE_MESSAGE", None):
                            with mock.patch.object(
                                avp.settings, "APP_UPDATE_STORE_ANDROID_URL", None
                            ):
                                with mock.patch.object(
                                    avp.settings, "APP_UPDATE_STORE_IOS_URL", None
                                ):
                                    p = avp.build_layer_b_payload()
        self.assertEqual(p["min_required_version"], "0.0.0")
        self.assertEqual(p["latest_version"], "1.2.0")


if __name__ == "__main__":
    unittest.main()
