"""Validation tests for the ``[sources]`` configuration table.

These settings decide how long an adapter waits for a provider and which
MediaCloud collections it searches. A wrong value here fails every search, so
it must be rejected when the application starts rather than at request time.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from news.sources.settings import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_MEDIACLOUD_COLLECTIONS,
    DEFAULT_READ_TIMEOUT_SECONDS,
)
from news.web.config import SettingsError, load_settings


def _load(table_text: str):
    """Load settings from a temporary file holding one configuration table."""
    with TemporaryDirectory() as temporary_directory:
        config_path = Path(temporary_directory) / "sources.toml"
        config_path.write_text(table_text, encoding="utf-8")
        return load_settings(config_path)


class SourceSettingsDefaultTests(unittest.TestCase):
    """The packaged defaults must be usable with no operator file at all."""

    def test_packaged_defaults_match_the_source_layer(self) -> None:
        """Two copies of a default would drift apart without this check."""
        with (
            TemporaryDirectory() as temporary_directory,
            patch("pathlib.Path.cwd", return_value=Path(temporary_directory)),
            patch.dict("os.environ", {}, clear=True),
        ):
            settings = load_settings()

        self.assertEqual(
            settings.sources.connect_timeout_seconds,
            DEFAULT_CONNECT_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            settings.sources.read_timeout_seconds,
            DEFAULT_READ_TIMEOUT_SECONDS,
        )
        self.assertEqual(
            settings.sources.mediacloud_collections,
            DEFAULT_MEDIACLOUD_COLLECTIONS,
        )

    def test_connect_timeout_covers_a_slow_tls_handshake(self) -> None:
        """The handshake to GDELT measured 12.5 seconds from the deployment."""
        self.assertGreater(DEFAULT_CONNECT_TIMEOUT_SECONDS, 12.5)


class SourceSettingsValidationTests(unittest.TestCase):
    """Bad values must name the setting rather than fail later as a timeout."""

    def test_operator_values_are_applied(self) -> None:
        """A partial table should change only the settings it names."""
        settings = _load(
            "[sources]\n"
            "connect_timeout_seconds = 8.5\n"
            "mediacloud_collections = [34412234, 34412476]\n"
        )

        self.assertEqual(settings.sources.connect_timeout_seconds, 8.5)
        self.assertEqual(settings.sources.read_timeout_seconds, 20.0)
        self.assertEqual(
            settings.sources.mediacloud_collections,
            (34412234, 34412476),
        )

    def test_zero_timeout_is_rejected(self) -> None:
        """A zero timeout would fail every request before it was sent."""
        with self.assertRaises(SettingsError) as raised:
            _load("[sources]\nconnect_timeout_seconds = 0\n")

        self.assertIn("sources.connect_timeout_seconds", str(raised.exception))

    def test_negative_read_timeout_is_rejected(self) -> None:
        """A negative wait has no meaning."""
        with self.assertRaises(SettingsError) as raised:
            _load("[sources]\nread_timeout_seconds = -3\n")

        self.assertIn("sources.read_timeout_seconds", str(raised.exception))

    def test_empty_collection_list_is_rejected(self) -> None:
        """MediaCloud answers HTTP 422 when a search names no collection."""
        with self.assertRaises(SettingsError) as raised:
            _load("[sources]\nmediacloud_collections = []\n")

        self.assertIn("sources.mediacloud_collections", str(raised.exception))

    def test_non_numeric_collection_is_rejected(self) -> None:
        """Collections are identified by number, not by name."""
        with self.assertRaises(SettingsError) as raised:
            _load('[sources]\nmediacloud_collections = ["United States"]\n')

        self.assertIn("whole numbers", str(raised.exception))

    def test_duplicate_collection_is_rejected(self) -> None:
        """A repeated collection would only search the same outlets twice."""
        with self.assertRaises(SettingsError) as raised:
            _load("[sources]\nmediacloud_collections = [34412234, 34412234]\n")

        self.assertIn("duplicates", str(raised.exception))

    def test_misspelled_key_is_rejected(self) -> None:
        """A silently ignored setting looks like the code failed to apply it."""
        with self.assertRaises(SettingsError) as raised:
            _load("[sources]\nconnect_timeout = 30\n")

        self.assertIn("connect_timeout", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
