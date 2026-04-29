"""Tests for version.json loading (app update / shipped semver metadata)."""

import json
import tempfile
import unittest
from pathlib import Path

from app.utils.shipped_app_version import (
    default_play_store_url,
    load_shipped_version,
)


class TestShippedAppVersion(unittest.TestCase):
    def test_missing_file_returns_nulls(self):
        p = Path(tempfile.gettempdir()) / "nonexistent_version_json_xxxx.json"
        if p.exists():
            p.unlink()
        self.assertEqual(
            load_shipped_version(p),
            {
                "version": None,
                "androidVersionCode": None,
                "buildNumber": None,
            },
        )

    def test_reads_expo_style_keys(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(
                {
                    "version": "2.3.0",
                    "androidVersionCode": 2300,
                    "buildNumber": "42",
                },
                f,
            )
            path = Path(f.name)
        try:
            data = load_shipped_version(path)
            self.assertEqual(data["version"], "2.3.0")
            self.assertEqual(data["androidVersionCode"], 2300)
            self.assertEqual(data["buildNumber"], "42")
        finally:
            path.unlink(missing_ok=True)

    def test_snake_case_aliases(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(
                {
                    "version": "1.2.3",
                    "android_version_code": "99",
                    "build_number": "beta",
                },
                f,
            )
            path = Path(f.name)
        try:
            data = load_shipped_version(path)
            self.assertEqual(data["androidVersionCode"], 99)
            self.assertEqual(data["buildNumber"], "beta")
        finally:
            path.unlink(missing_ok=True)

    def test_play_store_default_includes_package_id(self):
        url = default_play_store_url()
        self.assertIn("com.saimonsoft.customcoverlettermobile.app", url)


if __name__ == "__main__":
    unittest.main()
