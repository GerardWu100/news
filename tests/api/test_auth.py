"""Sign-in, sign-out, and the guard that closes every data route."""

from __future__ import annotations

import re
import unittest
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from news.api.app import create_app
from news.api.auth import MAX_FAILED_ATTEMPTS, SESSION_COOKIE_NAME
from news.sources import SourceQueryReport
from news.sources.base import Article, SourceSearchOptions
from news.web.config import load_settings
from tests.fixtures.authentication import (
    SECOND_TEST_PASSWORD,
    SECOND_TEST_USERNAME,
    TEST_PASSWORD,
    TEST_USERNAME,
    attach_session_cookie,
    basic_auth_headers,
    build_login_sessions,
)
from tests.fixtures.search_results import build_provider_response

PROTECTED_PATHS = (
    "/api/config",
    "/api/sources",
    "/api/search",
    "/api/export/csv",
    "/api/export/json",
)
_HIDDEN_FIELD_PATTERN = re.compile(r'<input type="hidden" name="(\w+)" value="([^"]*)"')


async def _offline_search_executor(
    _options: SourceSearchOptions,
    _source_names: Sequence[str] | None,
) -> tuple[list[Article], list[SourceQueryReport]]:
    """Return one offline provider page instead of calling the network."""
    return build_provider_response()


class AuthenticationTestCase(unittest.TestCase):
    """Shared setup: one application with a temporary account."""

    def setUp(self) -> None:
        """Build an application whose account lives in a temporary directory."""
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.data_directory = Path(temporary_directory.name)
        self.login_sessions = build_login_sessions(self.data_directory)
        self.application = create_app(
            load_settings(),
            search_executor=_offline_search_executor,
            login_sessions=self.login_sessions,
        )
        self.client = TestClient(self.application)

    def submit_sign_in_form(self, username: str, password: str) -> object:
        """Load the form, then post it back with its one-time token."""
        form_page = self.client.get("/login")
        hidden_fields = dict(_HIDDEN_FIELD_PATTERN.findall(form_page.text))
        return self.client.post(
            "/login",
            data={
                "username": username,
                "password": password,
                "form_token": hidden_fields["form_token"],
                "form_token_id": hidden_fields["form_token_id"],
            },
            follow_redirects=False,
        )


class SignedOutAccessTests(AuthenticationTestCase):
    """Verify that a signed-out caller sees no data."""

    def test_data_routes_answer_401(self) -> None:
        """Every route that returns news requires an account."""
        for path in PROTECTED_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)

    def test_401_does_not_ask_the_browser_for_a_password(self) -> None:
        """Without this header the browser shows our page, not its own box."""
        response = self.client.get("/api/config")

        self.assertNotIn("www-authenticate", response.headers)

    def test_root_redirects_to_the_sign_in_page(self) -> None:
        """A signed-out browser is sent to the form rather than the app shell."""
        response = self.client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/login")

    def test_health_check_and_static_files_stay_open(self) -> None:
        """Neither reveals search results, and the container needs the first."""
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/static/favicon.svg").status_code, 200)

    def test_guarded_html_is_not_reachable_through_static_paths(self) -> None:
        """Public assets must not expose alternate URLs for protected pages."""
        guarded_paths = (
            "/static/index.html",
            "/static/docs.html",
            "/static/GUIDE_static.md",
        )
        for path in guarded_paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_sign_in_page_carries_a_one_time_token(self) -> None:
        """The form must arrive with the token the server will check."""
        response = self.client.get("/login")
        hidden_fields = dict(_HIDDEN_FIELD_PATTERN.findall(response.text))

        self.assertEqual(response.status_code, 200)
        self.assertIn("form_token", hidden_fields)
        self.assertIn("form_token_id", hidden_fields)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'none'", response.headers["Content-Security-Policy"])


class SignInTests(AuthenticationTestCase):
    """Verify the form path from a submitted password to a working session."""

    def test_correct_password_starts_a_session(self) -> None:
        """A successful sign-in sets the cookie and opens the data routes."""
        response = self.submit_sign_in_form(TEST_USERNAME, TEST_PASSWORD)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/")
        self.assertIn(SESSION_COOKIE_NAME, response.cookies)
        self.assertEqual(self.client.get("/api/config").status_code, 200)

    def test_second_account_signs_in_as_itself(self) -> None:
        """Any configured account opens the data routes under its own name."""
        response = self.submit_sign_in_form(
            SECOND_TEST_USERNAME,
            SECOND_TEST_PASSWORD,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/api/config").status_code, 200)
        self.assertEqual(
            self.client.get("/api/session").json()["username"],
            SECOND_TEST_USERNAME,
        )

    def test_one_account_password_does_not_open_another(self) -> None:
        """Accounts are separate people, so their passwords must not cross."""
        response = self.submit_sign_in_form(SECOND_TEST_USERNAME, TEST_PASSWORD)

        self.assertEqual(response.headers["location"], "/login?reason=bad_credentials")
        self.assertEqual(self.client.get("/api/config").status_code, 401)

    def test_wrong_password_returns_to_the_form(self) -> None:
        """A failure names neither which half was wrong nor the account."""
        response = self.submit_sign_in_form(TEST_USERNAME, "not-the-password")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], "/login?reason=bad_credentials")
        self.assertEqual(self.client.get("/api/config").status_code, 401)

    def test_wrong_username_looks_identical_to_a_wrong_password(self) -> None:
        """The two failures must not be distinguishable from the response."""
        wrong_username = self.submit_sign_in_form("someone-else", TEST_PASSWORD)
        wrong_password = self.submit_sign_in_form(TEST_USERNAME, "not-the-password")

        self.assertEqual(
            wrong_username.headers["location"],
            wrong_password.headers["location"],
        )

    def test_a_form_token_works_only_once(self) -> None:
        """Replaying a captured submission is refused."""
        form_page = self.client.get("/login")
        hidden_fields = dict(_HIDDEN_FIELD_PATTERN.findall(form_page.text))
        submission = {
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
            "form_token": hidden_fields["form_token"],
            "form_token_id": hidden_fields["form_token_id"],
        }

        first = self.client.post("/login", data=submission, follow_redirects=False)
        second = self.client.post("/login", data=submission, follow_redirects=False)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.headers["location"], "/login?reason=expired_form")

    def test_repeated_failures_ban_the_client(self) -> None:
        """Guessing is slowed by refusing the address for a while."""
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.submit_sign_in_form(TEST_USERNAME, "not-the-password")

        banned_response = self.submit_sign_in_form(TEST_USERNAME, TEST_PASSWORD)

        self.assertEqual(banned_response.headers["location"], "/login?reason=banned")
        form_page = self.client.get("/login")
        self.assertIn("Too many failed attempts", form_page.text)

    def test_signed_in_browser_is_sent_past_the_form(self) -> None:
        """Reopening the sign-in page with a live session lands on the app."""
        attach_session_cookie(self.client, self.login_sessions)

        response = self.client.get("/login", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/")


class SignOutTests(AuthenticationTestCase):
    """Verify that signing out ends the session and needs its own token."""

    def test_sign_out_ends_the_session(self) -> None:
        """After signing out the same browser is refused again."""
        attach_session_cookie(self.client, self.login_sessions)
        sign_out_token = self.client.get("/api/session").json()["sign_out_token"]

        response = self.client.post(
            "/logout",
            data={"sign_out_token": sign_out_token},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.client.get("/api/config").status_code, 401)

    def test_sign_out_without_the_token_is_refused(self) -> None:
        """Another site must not be able to sign the reader out."""
        attach_session_cookie(self.client, self.login_sessions)

        response = self.client.post(
            "/logout",
            data={"sign_out_token": "forged"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/config").status_code, 200)

    def test_session_endpoint_reports_the_account(self) -> None:
        """The browser page reads the account name from here."""
        attach_session_cookie(self.client, self.login_sessions)

        payload = self.client.get("/api/session").json()

        self.assertEqual(payload["username"], TEST_USERNAME)
        self.assertTrue(payload["sign_out_token"])


class HeaderCredentialTests(AuthenticationTestCase):
    """Verify the HTTP Basic path the command line uses."""

    def test_correct_header_opens_the_data_routes(self) -> None:
        """One header, no cookie, and the request is served."""
        response = self.client.get("/api/config", headers=basic_auth_headers())

        self.assertEqual(response.status_code, 200)

    def test_second_account_header_opens_the_data_routes(self) -> None:
        """The command line may sign in as any configured account."""
        response = self.client.get(
            "/api/config",
            headers=basic_auth_headers(SECOND_TEST_USERNAME, SECOND_TEST_PASSWORD),
        )

        self.assertEqual(response.status_code, 200)

    def test_wrong_header_is_refused(self) -> None:
        """A wrong password in the header is no better than in the form."""
        response = self.client.get(
            "/api/config",
            headers=basic_auth_headers(TEST_USERNAME, "not-the-password"),
        )

        self.assertEqual(response.status_code, 401)

    def test_malformed_header_is_refused(self) -> None:
        """Values that are not Basic credentials are rejected, not decoded."""
        for header_value in ("Bearer abc", "Basic !!!not-base64!!!", "Basic"):
            with self.subTest(header=header_value):
                response = self.client.get(
                    "/api/config",
                    headers={"Authorization": header_value},
                )
                self.assertEqual(response.status_code, 401)

    def test_header_failures_count_toward_the_ban(self) -> None:
        """The limit cannot be sidestepped by guessing through this path."""
        wrong_header = basic_auth_headers(TEST_USERNAME, "not-the-password")
        for _ in range(MAX_FAILED_ATTEMPTS):
            self.client.get("/api/config", headers=wrong_header)

        response = self.client.get("/api/config", headers=basic_auth_headers())

        self.assertEqual(response.status_code, 401)


class UnconfiguredAccountTests(unittest.TestCase):
    """Verify that a server without an account serves nothing."""

    def test_missing_account_closes_every_data_route(self) -> None:
        """No credentials file must mean closed, never open."""
        with TemporaryDirectory() as temporary_directory:
            sessions = build_login_sessions(Path(temporary_directory))
            sessions.credentials_file.unlink()
            client = TestClient(
                create_app(
                    load_settings(),
                    search_executor=_offline_search_executor,
                    login_sessions=sessions,
                )
            )

            response = client.get("/api/config")

            self.assertEqual(response.status_code, 401)
            self.assertIn("not configured", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
