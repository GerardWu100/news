"""Credentials that the command line sends to a protected server."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from news.cli.fetch import api_credentials, fetch_api_page
from news.cli.output import download_api_export
from news.cli.parser import build_arg_parser
from news.web.credentials import ENV_PASSWORD_KEY, ENV_USERNAME_KEY


class ApiCredentialTests(unittest.TestCase):
    """Verify which settings become the request's sign-in details."""

    def test_both_settings_present_gives_a_username_and_password(self) -> None:
        """The command line signs in with the same account as the browser."""
        with patch.dict(
            "os.environ",
            {ENV_USERNAME_KEY: "analyst", ENV_PASSWORD_KEY: "a-real-password"},
            clear=True,
        ):
            self.assertEqual(api_credentials(), ("analyst", "a-real-password"))

    def test_missing_settings_send_nothing(self) -> None:
        """A half-configured account is left to the server to refuse."""
        for environment in (
            {},
            {ENV_USERNAME_KEY: "analyst"},
            {ENV_PASSWORD_KEY: "a-real-password"},
            {ENV_USERNAME_KEY: "   ", ENV_PASSWORD_KEY: "a-real-password"},
        ):
            with self.subTest(environment=environment):
                with patch.dict("os.environ", environment, clear=True):
                    self.assertIsNone(api_credentials())


class SentCredentialTests(unittest.TestCase):
    """Verify that every route needing the account actually receives it."""

    def test_search_and_export_requests_both_carry_the_account(self) -> None:
        """The download routes are protected exactly like the search route."""
        environment = {
            ENV_USERNAME_KEY: "analyst",
            ENV_PASSWORD_KEY: "a-real-password",
        }
        with patch.dict("os.environ", environment, clear=True):
            args = build_arg_parser().parse_args(
                ["inflation", "-s", "2025-01-01", "-e", "2025-03-01", "--export", "csv"]
            )

            for description, call_under_test in (
                ("search", lambda: fetch_api_page(args, page=1)),
                ("export", lambda: download_api_export(args)),
            ):
                with self.subTest(route=description):
                    recorder = _RecordingClientFactory()
                    with patch("news.cli.fetch.httpx.Client", recorder):
                        call_under_test()
                    self.assertEqual(
                        recorder.auth,
                        ("analyst", "a-real-password"),
                    )


class RejectedCredentialTests(unittest.TestCase):
    """Verify the message shown when the server refuses the account."""

    def test_refused_requests_name_the_two_settings_to_fix(self) -> None:
        """A raw 401 would not tell the reader what to change."""
        with patch.dict("os.environ", {}, clear=True):
            args = build_arg_parser().parse_args(
                ["inflation", "-s", "2025-01-01", "-e", "2025-03-01", "--export", "csv"]
            )

            for description, call_under_test in (
                ("search", lambda: fetch_api_page(args, page=1)),
                ("export", lambda: download_api_export(args)),
            ):
                with self.subTest(route=description):
                    with patch("news.cli.fetch.httpx.Client", _RefusingClient):
                        with self.assertRaises(RuntimeError) as raised_error:
                            call_under_test()

                    message = str(raised_error.exception)
                    self.assertIn(ENV_USERNAME_KEY, message)
                    self.assertIn(ENV_PASSWORD_KEY, message)


class _RefusingClient:
    """Stand-in HTTP client that answers every request with 401."""

    def __init__(self, *_args: object, **_keyword_args: object) -> None:
        pass

    def __enter__(self) -> _RefusingClient:
        return self

    def __exit__(self, *_exception_details: object) -> bool:
        return False

    def get(self, *_args: object, **_keyword_args: object) -> SimpleNamespace:
        """Return the smallest response the caller inspects."""
        return SimpleNamespace(status_code=401)


class _RecordingClientFactory:
    """Stand-in client that remembers the credentials it was built with."""

    def __init__(self) -> None:
        self.auth: object = None

    def __call__(self, *_args: object, **keyword_args: object) -> _RecordingClient:
        """Record the account and return a client that answers every request."""
        self.auth = keyword_args.get("auth")
        return _RecordingClient()


class _RecordingClient:
    """Stand-in HTTP client that answers with the smallest usable response."""

    def __enter__(self) -> _RecordingClient:
        return self

    def __exit__(self, *_exception_details: object) -> bool:
        return False

    def get(self, *_args: object, **_keyword_args: object) -> SimpleNamespace:
        """Return a successful response for both the search and export routes."""
        return SimpleNamespace(
            status_code=200,
            text="title,url\n",
            json=lambda: {"results": [], "meta": {}},
            raise_for_status=lambda: None,
        )


if __name__ == "__main__":
    unittest.main()
