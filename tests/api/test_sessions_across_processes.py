"""Sessions shared between two processes serving the same data directory.

Each worker process builds its own :class:`LoginSessions`. Two instances
pointed at one data directory stand in for that here: if a session created by
one is invisible to the other, a browser signed in through the first worker is
refused by the second.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from news.api.auth import SESSION_COOKIE_NAME
from tests.fixtures.authentication import build_login_sessions


def _request_with_cookie(session_id: str) -> SimpleNamespace:
    """Build the smallest object the session helpers read."""
    return SimpleNamespace(cookies={SESSION_COOKIE_NAME: session_id})


class SharedSessionTests(unittest.TestCase):
    """Verify that two workers agree about who is signed in."""

    def setUp(self) -> None:
        """Point two independent instances at one data directory."""
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.data_directory = Path(temporary_directory.name)
        self.first_worker = build_login_sessions(self.data_directory)
        self.second_worker = build_login_sessions(self.data_directory)

    def test_a_session_started_on_one_worker_is_accepted_by_the_other(self) -> None:
        """Otherwise a browser is signed in or out depending on which answers."""
        session_id = self.first_worker.start_session()
        request = _request_with_cookie(session_id)

        self.assertTrue(self.first_worker.session_is_valid(request))
        self.assertTrue(self.second_worker.session_is_valid(request))

    def test_signing_out_on_one_worker_ends_it_everywhere(self) -> None:
        """A sign-out that only half works is worse than none at all."""
        session_id = self.first_worker.start_session()
        request = _request_with_cookie(session_id)

        self.second_worker.end_session(session_id)

        self.assertFalse(self.first_worker.session_is_valid(request))
        self.assertFalse(self.second_worker.session_is_valid(request))

    def test_a_sign_out_form_built_by_one_worker_is_accepted_by_the_other(
        self,
    ) -> None:
        """The page and the submission need not reach the same process."""
        session_id = self.first_worker.start_session()
        request = _request_with_cookie(session_id)

        token = self.first_worker.sign_out_token(request)

        self.assertTrue(token)
        self.assertTrue(self.second_worker.sign_out_token_is_valid(request, token))

    def test_the_same_session_keeps_one_sign_out_token(self) -> None:
        """A second page load must not invalidate the first page's form."""
        session_id = self.first_worker.start_session()
        request = _request_with_cookie(session_id)

        first_token = self.first_worker.sign_out_token(request)
        second_token = self.second_worker.sign_out_token(request)

        self.assertEqual(first_token, second_token)

    def test_a_wrong_sign_out_token_is_refused(self) -> None:
        """The token is what stops another site from signing the user out."""
        session_id = self.first_worker.start_session()
        request = _request_with_cookie(session_id)
        self.first_worker.sign_out_token(request)

        self.assertFalse(
            self.second_worker.sign_out_token_is_valid(request, "wrong-token")
        )

    def test_starting_a_session_keeps_the_sessions_already_stored(self) -> None:
        """A second sign-in must not overwrite the first browser's session."""
        first_session = self.first_worker.start_session()
        second_session = self.second_worker.start_session()

        self.assertTrue(
            self.second_worker.session_is_valid(_request_with_cookie(first_session))
        )
        self.assertTrue(
            self.first_worker.session_is_valid(_request_with_cookie(second_session))
        )

    def test_an_unknown_cookie_is_refused(self) -> None:
        """A guessed identifier must not be mistaken for a stored session."""
        request = _request_with_cookie("not-a-real-session-identifier")

        self.assertFalse(self.first_worker.session_is_valid(request))


if __name__ == "__main__":
    unittest.main()
