"""Validation tests for application settings."""

from __future__ import annotations

import dataclasses
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from news.web.config import SettingsError, load_settings


class SettingsLoadingTests(unittest.TestCase):
    """Verify defaults, overrides, and startup-focused error messages."""

    def test_missing_optional_config_uses_packaged_defaults(self) -> None:
        """No external file should produce validated package defaults."""
        with (
            TemporaryDirectory() as temporary_directory,
            patch("pathlib.Path.cwd", return_value=Path(temporary_directory)),
            patch.dict("os.environ", {}, clear=True),
        ):
            settings = load_settings()

        self.assertFalse(settings.frontend.default_english_only)
        self.assertEqual(settings.frontend.default_sources, ())
        self.assertEqual(settings.cache.ttl_seconds, 300)
        self.assertEqual(settings.cache.max_entries, 100)

    def test_partial_external_config_overrides_packaged_defaults(self) -> None:
        """Operators should only need to specify settings they change."""
        with TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "custom.toml"
            config_path.write_text(
                "[cache]\nttl_seconds = 45\n",
                encoding="utf-8",
            )

            settings = load_settings(config_path)

        self.assertEqual(settings.cache.ttl_seconds, 45)
        self.assertEqual(settings.cache.max_entries, 100)

    def test_malformed_toml_has_clear_error(self) -> None:
        """Malformed TOML should identify the selected configuration file."""
        with TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "broken.toml"
            config_path.write_text("[cache\n", encoding="utf-8")

            with self.assertRaises(SettingsError) as context:
                load_settings(config_path)

        self.assertIn("Malformed TOML", str(context.exception))
        self.assertIn("broken.toml", str(context.exception))

    def test_unknown_source_is_rejected(self) -> None:
        """Misspelled frontend provider names must fail at startup."""
        with TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "unknown-source.toml"
            config_path.write_text(
                '[frontend]\ndefault_sources = ["guardain"]\n',
                encoding="utf-8",
            )

            with self.assertRaises(SettingsError) as context:
                load_settings(config_path)

        self.assertIn("guardain", str(context.exception))

    def test_non_positive_cache_ttl_is_rejected(self) -> None:
        """Cache time-to-live values must be positive."""
        invalid_values = (0, -1)
        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                with TemporaryDirectory() as temporary_directory:
                    config_path = Path(temporary_directory) / "invalid-cache.toml"
                    config_path.write_text(
                        f"[cache]\nttl_seconds = {invalid_value}\n",
                        encoding="utf-8",
                    )

                    with self.assertRaises(SettingsError) as context:
                        load_settings(config_path)

                self.assertIn("cache.ttl_seconds", str(context.exception))

    def test_non_finite_trends_pacing_is_rejected(self) -> None:
        """NaN and infinity cannot become a meaningful request delay."""
        for invalid_value in ("nan", "+inf", "-inf"):
            with (
                self.subTest(invalid_value=invalid_value),
                TemporaryDirectory() as temporary_directory,
            ):
                config_path = Path(temporary_directory) / "invalid-trends.toml"
                config_path.write_text(
                    f"[trends]\nseconds_between_requests = {invalid_value}\n",
                    encoding="utf-8",
                )
                with self.assertRaises(SettingsError):
                    load_settings(config_path)

    def test_unknown_setting_key_is_rejected(self) -> None:
        """A misspelled key must not silently fall back to a default."""
        with TemporaryDirectory() as temporary_directory:
            config_path = Path(temporary_directory) / "misspelled.toml"
            config_path.write_text(
                "[cache]\nttl_second = 45\n",
                encoding="utf-8",
            )

            with self.assertRaises(SettingsError) as context:
                load_settings(config_path)

        self.assertIn("ttl_second", str(context.exception))

    def test_settings_are_immutable(self) -> None:
        """Validated settings should not change after application startup."""
        settings = load_settings()

        with self.assertRaises(dataclasses.FrozenInstanceError):
            settings.cache.ttl_seconds = 1  # type: ignore[misc]
