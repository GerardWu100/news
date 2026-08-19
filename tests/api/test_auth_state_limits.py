"""Limits that keep sign-in state from growing without end.

Both the failed-login file and the pending sign-in form tokens are written by
callers who have not proved anything yet, so both need a ceiling.
"""

from __future__ import annotations

import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from news.api.auth import (
    BAN_SECONDS,
    FAILURE_WINDOW_SECONDS,
    MAX_FAILED_ATTEMPTS,
    MAX_PENDING_FORM_TOKENS,
    _add_failure,
    _reset_failures,
)
from news.web.auth_store import JsonState
from tests.fixtures.authentication import build_login_sessions


class FailureRecordPruningTests(unittest.TestCase):
    """Verify that spent failed-login records are removed, not accumulated."""

    def test_a_spent_record_is_dropped_when_another_address_fails(self) -> None:
        """One row per address seen, kept forever, is a file that only grows."""
        long_ago = time.time() - (FAILURE_WINDOW_SECONDS + BAN_SECONDS + 60)
        state: JsonState = {
            "198.51.100.7": {
                "failed": 3,
                "last_failed": long_ago,
                "banned_until": 0,
            }
        }

        _add_failure(state, "203.0.113.9")

        self.assertNotIn("198.51.100.7", state)
        self.assertIn("203.0.113.9", state)

    def test_a_banned_address_survives_pruning(self) -> None:
        """Dropping a live ban would hand the attacker a fresh budget."""
        now = time.time()
        state: JsonState = {
            "198.51.100.7": {
                "failed": MAX_FAILED_ATTEMPTS,
                "last_failed": now,
                "banned_until": now + BAN_SECONDS,
            }
        }

        _add_failure(state, "203.0.113.9")

        self.assertIn("198.51.100.7", state)

    def test_a_recent_failure_survives_pruning(self) -> None:
        """A count inside the rolling window still has to add up to a ban."""
        state: JsonState = {}
        for _attempt in range(MAX_FAILED_ATTEMPTS - 1):
            _add_failure(state, "198.51.100.7")
        _add_failure(state, "203.0.113.9")

        self.assertEqual(state["198.51.100.7"]["failed"], MAX_FAILED_ATTEMPTS - 1)

    def test_a_successful_sign_in_removes_the_row_entirely(self) -> None:
        """A zeroed row records nothing and still costs a line in the file."""
        state: JsonState = {}
        _add_failure(state, "198.51.100.7")

        _reset_failures(state, "198.51.100.7")

        self.assertEqual(state, {})

    def test_an_unreadable_record_is_discarded(self) -> None:
        """A record that cannot be parsed cannot be trusted to hold a ban."""
        state: JsonState = {"198.51.100.7": {"last_failed": "not-a-number"}}

        _add_failure(state, "203.0.113.9")

        self.assertNotIn("198.51.100.7", state)


class FormTokenLimitTests(unittest.TestCase):
    """Verify the ceiling on tokens issued to callers who never sign in."""

    def setUp(self) -> None:
        """Build sign-in state backed by a temporary directory."""
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.sessions = build_login_sessions(Path(temporary_directory.name))

    def test_pending_tokens_stop_at_the_cap(self) -> None:
        """Requesting sign-in forms in a loop must not exhaust memory."""
        for _request in range(MAX_PENDING_FORM_TOKENS + 50):
            self.sessions.issue_form_token()

        stored_tokens = self.sessions.auth_store.update_form_tokens(
            lambda _tokens: None
        )
        self.assertLessEqual(
            len(stored_tokens),
            MAX_PENDING_FORM_TOKENS,
        )

    def test_the_newest_token_still_works_after_the_cap_is_reached(self) -> None:
        """A real person signing in must not be pushed out by a flood."""
        for _request in range(MAX_PENDING_FORM_TOKENS):
            self.sessions.issue_form_token()
        token_id, token = self.sessions.issue_form_token()

        self.assertTrue(self.sessions.consume_form_token(token_id, token))

    def test_a_consumed_token_cannot_be_used_twice(self) -> None:
        """One form submission per issued token, so a replay is refused."""
        token_id, token = self.sessions.issue_form_token()

        self.assertTrue(self.sessions.consume_form_token(token_id, token))
        self.assertFalse(self.sessions.consume_form_token(token_id, token))


if __name__ == "__main__":
    unittest.main()
