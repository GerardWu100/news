"""Startup rules that turn the operator's account settings into a stored hash."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from news.web.credentials import (
    ENV_PASSWORD_KEY,
    ENV_USERNAME_KEY,
    load_ui_credentials,
    sync_ui_credentials,
)
from news.web.passwords import verify_password
from news.web.paths import CREDENTIALS_FILENAME, SESSION_STATE_FILENAME


class CredentialSyncTests(unittest.TestCase):
    """Verify the credential file follows the environment on every startup."""

    def setUp(self) -> None:
        """Give each test its own data directory."""
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.data_directory = Path(temporary_directory.name)
        self.credentials_file = self.data_directory / CREDENTIALS_FILENAME
        self.session_file = self.data_directory / SESSION_STATE_FILENAME

    def _sync(self, username: str | None, password: str | None) -> str:
        """Run one startup sync with the given account settings.

        ``None`` stands for an unset setting, which the process environment
        represents as an empty value.
        """
        environment = {
            ENV_USERNAME_KEY: username or "",
            ENV_PASSWORD_KEY: password or "",
        }
        with patch.dict("os.environ", environment):
            return sync_ui_credentials(self.data_directory)

    def test_first_startup_writes_a_verifiable_hash(self) -> None:
        """A new account produces an owner-only file the password verifies against."""
        status = self._sync("analyst", "first-password")

        stored = load_ui_credentials(self.credentials_file)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored[0], "analyst")
        self.assertTrue(verify_password("first-password", stored[1]))
        self.assertIn("analyst", status)
        self.assertEqual(self.credentials_file.stat().st_mode & 0o777, 0o600)

    def test_unchanged_password_leaves_the_file_alone(self) -> None:
        """A restart with the same account keeps the existing hash."""
        self._sync("analyst", "first-password")
        first_contents = self.credentials_file.read_text(encoding="utf-8")

        status = self._sync("analyst", "first-password")

        self.assertEqual(
            self.credentials_file.read_text(encoding="utf-8"),
            first_contents,
        )
        self.assertIn("verified", status)

    def test_changed_password_rewrites_the_hash_and_drops_sessions(self) -> None:
        """A new password must not leave old browsers signed in."""
        self._sync("analyst", "first-password")
        self.session_file.write_text(
            json.dumps({"old": {"created_at": 1}}),
            encoding="utf-8",
        )

        self._sync("analyst", "second-password")

        stored = load_ui_credentials(self.credentials_file)
        assert stored is not None
        self.assertTrue(verify_password("second-password", stored[1]))
        self.assertFalse(verify_password("first-password", stored[1]))
        self.assertFalse(self.session_file.exists())

    def test_missing_settings_remove_the_stored_account(self) -> None:
        """Clearing the settings must close the server, not leave it open."""
        self._sync("analyst", "first-password")
        self.session_file.write_text(
            json.dumps({"old": {"created_at": 1}}),
            encoding="utf-8",
        )

        status = self._sync(None, None)

        self.assertFalse(self.credentials_file.exists())
        self.assertFalse(self.session_file.exists())
        self.assertIn(ENV_USERNAME_KEY, status)

    def test_example_password_is_called_out(self) -> None:
        """Leaving the shipped example password in place earns a warning."""
        status = self._sync("analyst", "changeme")

        self.assertIn("WARNING", status)

    def test_damaged_credential_file_reads_as_no_account(self) -> None:
        """A truncated or hand-edited file disables sign-in instead of raising."""
        self.credentials_file.write_text("{not json", encoding="utf-8")

        self.assertIsNone(load_ui_credentials(self.credentials_file))


if __name__ == "__main__":
    unittest.main()
