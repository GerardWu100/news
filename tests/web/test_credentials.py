"""Startup rules that turn the operator's account settings into stored hashes."""

from __future__ import annotations

import json
import os
import unittest
from multiprocessing import get_context
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from news.web.credentials import (
    ENV_PASSWORD_KEY,
    ENV_USERNAME_KEY,
    MAX_ACCOUNTS,
    account_env_keys,
    load_ui_accounts,
    sync_ui_credentials,
)
from news.web.passwords import verify_password
from news.web.paths import CREDENTIALS_FILENAME, SESSION_STATE_FILENAME


def _concurrent_credential_sync(data_directory: str, start_gate: Any) -> None:
    """Run one credential sync after every test worker reaches the barrier.

    Parameters
    ----------
    data_directory : str
        Shared temporary directory used by all worker processes.
    start_gate : Any
        Multiprocessing barrier whose ``wait`` method releases workers together.
    """
    os.environ[ENV_USERNAME_KEY] = "analyst"
    os.environ[ENV_PASSWORD_KEY] = "concurrent-password"
    start_gate.wait()
    sync_ui_credentials(Path(data_directory))


class CredentialSyncTests(unittest.TestCase):
    """Verify the credential file follows the environment on every startup."""

    def setUp(self) -> None:
        """Give each test its own data directory."""
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.data_directory = Path(temporary_directory.name)
        self.credentials_file = self.data_directory / CREDENTIALS_FILENAME
        self.session_file = self.data_directory / SESSION_STATE_FILENAME

    def _sync(self, *accounts: tuple[str | None, str | None]) -> str:
        """Run one startup sync with the given account slots.

        Parameters
        ----------
        *accounts : tuple[str | None, str | None]
            ``(username, password)`` per slot, in slot order. ``None`` stands
            for an unset setting, which the process environment represents as
            an empty value. Slots beyond the ones given are cleared, so a test
            never inherits a value from the real environment.

        Returns
        -------
        str
            The status line the sync produced.
        """
        environment: dict[str, str] = {}
        for slot in range(1, MAX_ACCOUNTS + 1):
            username_key, password_key = account_env_keys(slot)
            username, password = (
                accounts[slot - 1] if slot <= len(accounts) else (None, None)
            )
            environment[username_key] = username or ""
            environment[password_key] = password or ""
        with patch.dict("os.environ", environment):
            return sync_ui_credentials(self.data_directory)

    def test_first_startup_writes_a_verifiable_hash(self) -> None:
        """A new account produces an owner-only file its password verifies against."""
        status = self._sync(("analyst", "first-password"))

        stored = load_ui_accounts(self.credentials_file)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0].username, "analyst")
        self.assertTrue(verify_password("first-password", stored[0].password_hash))
        self.assertIn("analyst", status)
        self.assertEqual(self.credentials_file.stat().st_mode & 0o777, 0o600)

    def test_three_accounts_are_all_stored(self) -> None:
        """Every filled slot becomes an account with its own hash."""
        self._sync(
            ("analyst", "first-password"),
            ("colleague", "second-password"),
            ("intern", "third-password"),
        )

        stored = load_ui_accounts(self.credentials_file)

        self.assertEqual(
            [account.username for account in stored],
            ["analyst", "colleague", "intern"],
        )
        self.assertTrue(verify_password("second-password", stored[1].password_hash))
        self.assertTrue(verify_password("third-password", stored[2].password_hash))
        self.assertFalse(verify_password("second-password", stored[2].password_hash))

    def test_a_gap_between_slots_is_allowed(self) -> None:
        """Using slots one and three, and leaving two blank, keeps both accounts."""
        self._sync(
            ("analyst", "first-password"),
            (None, None),
            ("intern", "third-password"),
        )

        stored = load_ui_accounts(self.credentials_file)

        self.assertEqual(
            [account.username for account in stored],
            ["analyst", "intern"],
        )

    def test_half_filled_slot_is_ignored_with_a_warning(self) -> None:
        """A name without a password must not create an account."""
        status = self._sync(
            ("analyst", "first-password"),
            ("colleague", None),
        )

        stored = load_ui_accounts(self.credentials_file)

        self.assertEqual([account.username for account in stored], ["analyst"])
        self.assertIn("WARNING", status)

    def test_repeated_account_name_is_ignored_with_a_warning(self) -> None:
        """Two slots sharing a name would make the second unreachable."""
        status = self._sync(
            ("analyst", "first-password"),
            ("analyst", "second-password"),
        )

        stored = load_ui_accounts(self.credentials_file)

        self.assertEqual(len(stored), 1)
        self.assertTrue(verify_password("first-password", stored[0].password_hash))
        self.assertIn("WARNING", status)

    def test_unchanged_accounts_leave_the_file_alone(self) -> None:
        """A restart with the same accounts keeps the existing hashes."""
        self._sync(("analyst", "first-password"), ("colleague", "second-password"))
        first_contents = self.credentials_file.read_text(encoding="utf-8")

        status = self._sync(
            ("analyst", "first-password"),
            ("colleague", "second-password"),
        )

        self.assertEqual(
            self.credentials_file.read_text(encoding="utf-8"),
            first_contents,
        )
        self.assertIn("verified", status)

    def test_changed_password_rewrites_the_hash_and_drops_sessions(self) -> None:
        """A new password must not leave old browsers signed in."""
        self._sync(("analyst", "first-password"))
        self.session_file.write_text(
            json.dumps({"old": {"created_at": 1}}),
            encoding="utf-8",
        )

        self._sync(("analyst", "second-password"))

        stored = load_ui_accounts(self.credentials_file)
        self.assertTrue(verify_password("second-password", stored[0].password_hash))
        self.assertFalse(verify_password("first-password", stored[0].password_hash))
        self.assertFalse(self.session_file.exists())

    def test_removing_an_account_rewrites_the_file_and_drops_sessions(self) -> None:
        """A deleted account must lose its stored hash and any live session."""
        self._sync(("analyst", "first-password"), ("colleague", "second-password"))
        self.session_file.write_text(
            json.dumps({"old": {"created_at": 1}}),
            encoding="utf-8",
        )

        self._sync(("analyst", "first-password"))

        stored = load_ui_accounts(self.credentials_file)
        self.assertEqual([account.username for account in stored], ["analyst"])
        self.assertFalse(self.session_file.exists())

    def test_missing_settings_remove_the_stored_accounts(self) -> None:
        """Clearing the settings must close the server, not leave it open."""
        self._sync(("analyst", "first-password"))
        self.session_file.write_text(
            json.dumps({"old": {"created_at": 1}}),
            encoding="utf-8",
        )

        status = self._sync()

        self.assertFalse(self.credentials_file.exists())
        self.assertFalse(self.session_file.exists())
        self.assertIn(ENV_USERNAME_KEY, status)
        self.assertIn(ENV_PASSWORD_KEY, status)

    def test_example_password_is_called_out(self) -> None:
        """Leaving the shipped example password in place earns a warning."""
        status = self._sync(("analyst", "changeme"))

        self.assertIn("WARNING", status)

    def test_damaged_credential_file_reads_as_no_account(self) -> None:
        """A truncated or hand-edited file disables sign-in instead of raising."""
        self.credentials_file.write_text("{not json", encoding="utf-8")
        self.assertEqual(load_ui_accounts(self.credentials_file), [])

        self.credentials_file.write_text(
            json.dumps({"accounts": [{"username": "analyst"}]}),
            encoding="utf-8",
        )
        self.assertEqual(load_ui_accounts(self.credentials_file), [])

        self.credentials_file.write_text(json.dumps({"accounts": {}}), encoding="utf-8")
        self.assertEqual(load_ui_accounts(self.credentials_file), [])

    def test_concurrent_startups_share_one_credentials_transaction(self) -> None:
        """Several workers starting together must not rename one temp file."""
        process_count = 4
        process_context = get_context("fork")
        start_gate = process_context.Barrier(process_count)
        processes = [
            process_context.Process(
                target=_concurrent_credential_sync,
                args=(str(self.data_directory), start_gate),
            )
            for _worker in range(process_count)
        ]

        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=10)

        self.assertEqual([process.exitcode for process in processes], [0] * process_count)
        self.assertEqual(len(load_ui_accounts(self.credentials_file)), 1)


if __name__ == "__main__":
    unittest.main()
