"""Offline tests for reusable ACLED OAuth behavior."""

from __future__ import annotations

import io
import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.parse import parse_qs
from urllib.request import Request

from news.sources.acled_oauth import (
    ENV_FILE_PERMISSION_MODE,
    OAuthConfig,
    extract_access_token,
    load_oauth_config,
    obtain_and_persist_token,
    persist_token_fields,
    request_oauth_token,
)

FIXED_TIME = datetime(2026, 7, 26, 15, 30, tzinfo=UTC)


def _build_config() -> OAuthConfig:
    """Return valid placeholder-free request settings."""
    return OAuthConfig(
        token_url="https://example.com/oauth/token",
        username="researcher@example.com",
        password="private-password",
        grant_type="password",
        client_id="acled",
    )


class OAuthConfigTests(unittest.TestCase):
    """Verify environment values fail before network work begins."""

    def test_load_oauth_config_requires_every_field(self) -> None:
        """A missing password should produce a field-specific error."""
        environment = {
            "ACLED_OAUTH_TOKEN_URL": "https://example.com/oauth/token",
            "ACLED_OAUTH_GRANT_TYPE": "password",
            "ACLED_OAUTH_CLIENT_ID": "acled",
            "ACLED_USERNAME": "researcher@example.com",
        }

        with self.assertRaisesRegex(ValueError, "ACLED_PASSWORD"):
            load_oauth_config(environment)

    def test_load_oauth_config_rejects_example_placeholders(self) -> None:
        """Credentials copied unchanged from `.env.example` are invalid."""
        environment = {
            "ACLED_OAUTH_TOKEN_URL": "https://example.com/oauth/token",
            "ACLED_OAUTH_GRANT_TYPE": "password",
            "ACLED_OAUTH_CLIENT_ID": "acled",
            "ACLED_USERNAME": "your_acled_email",
            "ACLED_PASSWORD": "your_acled_password",
        }

        with self.assertRaisesRegex(ValueError, "ACLED_USERNAME"):
            load_oauth_config(environment)

    def test_load_oauth_config_refuses_an_unencrypted_token_url(self) -> None:
        """The request body carries the account password in readable form."""
        for token_url in (
            "http://example.com/oauth/token",
            "example.com/oauth/token",
        ):
            with self.subTest(token_url=token_url):
                environment = {
                    "ACLED_OAUTH_TOKEN_URL": token_url,
                    "ACLED_OAUTH_GRANT_TYPE": "password",
                    "ACLED_OAUTH_CLIENT_ID": "acled",
                    "ACLED_USERNAME": "researcher@example.com",
                    "ACLED_PASSWORD": "private-password",
                }

                with self.assertRaisesRegex(ValueError, "https"):
                    load_oauth_config(environment)


class OAuthRequestTests(unittest.TestCase):
    """Verify request construction and network failure behavior."""

    def test_request_uses_form_body_and_injected_opener(self) -> None:
        """The package should send the documented password-grant form."""
        captured_request: Request | None = None
        captured_timeout: int | None = None

        def fake_opener(
            request: Request,
            *,
            timeout: int,
        ) -> io.BytesIO:
            """Capture the outbound request and return an offline response."""
            nonlocal captured_request, captured_timeout
            captured_request = request
            captured_timeout = timeout
            return io.BytesIO(json.dumps({"access_token": "secret-token"}).encode())

        payload = request_oauth_token(
            _build_config(),
            opener=fake_opener,
            timeout_seconds=12,
        )

        self.assertEqual(payload["access_token"], "secret-token")
        self.assertEqual(captured_timeout, 12)
        self.assertIsNotNone(captured_request)
        assert captured_request is not None
        form_values = parse_qs(captured_request.data.decode())
        self.assertEqual(form_values["username"], ["researcher@example.com"])
        self.assertEqual(form_values["grant_type"], ["password"])

    def test_http_errors_propagate_to_terminal_wrapper(self) -> None:
        """The package should preserve HTTP status and body for presentation."""
        expected_error = HTTPError(
            url="https://example.com/oauth/token",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=io.BytesIO(b"consent required"),
        )

        def failing_opener(
            _request: Request,
            *,
            timeout: int,
        ) -> io.BytesIO:
            """Raise a deterministic provider error without live networking."""
            raise expected_error

        with self.assertRaises(HTTPError) as context:
            request_oauth_token(_build_config(), opener=failing_opener)

        self.assertIs(context.exception, expected_error)


class OAuthPersistenceTests(unittest.TestCase):
    """Verify response variants and dotenv updates."""

    def test_extract_access_token_supports_provider_key_variants(self) -> None:
        """Known snake-case, generic, and camel-case keys should work."""
        variants = (
            ({"access_token": "first"}, "first"),
            ({"token": "second"}, "second"),
            ({"accessToken": "third"}, "third"),
        )

        for payload, expected_token in variants:
            with self.subTest(payload=payload):
                self.assertEqual(extract_access_token(payload), expected_token)

    def test_missing_access_token_is_rejected(self) -> None:
        """A successful-looking payload without a bearer value is invalid."""
        with TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"

            with self.assertRaisesRegex(ValueError, "access token"):
                persist_token_fields({}, env_file, clock=lambda: FIXED_TIME)

        self.assertFalse(env_file.exists())

    def test_persist_token_fields_updates_env_once_and_preserves_other_values(
        self,
    ) -> None:
        """Token persistence should replace duplicates and preserve comments."""
        with TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"
            env_file.write_text(
                "# Local credentials\n"
                "OTHER_KEY=keep-me\n"
                "ACLED_BEARER_TOKEN=old-one\n"
                "ACLED_BEARER_TOKEN=old-two\n",
                encoding="utf-8",
            )

            stored = persist_token_fields(
                {
                    "accessToken": "new-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "refresh_token": "refresh-me",
                },
                env_file,
                clock=lambda: FIXED_TIME,
            )
            contents = env_file.read_text(encoding="utf-8")

        self.assertEqual(stored.access_token, "new-token")
        self.assertEqual(stored.obtained_at_utc, "2026-07-26T15:30:00+00:00")
        self.assertIn("# Local credentials", contents)
        self.assertIn("OTHER_KEY=keep-me", contents)
        self.assertEqual(contents.count("ACLED_BEARER_TOKEN="), 1)
        self.assertIn("ACLED_BEARER_EXPIRES_IN=3600", contents)
        self.assertIn("ACLED_REFRESH_TOKEN=refresh-me", contents)

    def test_a_new_env_file_is_readable_only_by_its_owner(self) -> None:
        """It holds the sign-in password, provider keys, and the ACLED token."""
        with TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"

            persist_token_fields(
                {"access_token": "new-token"},
                env_file,
                clock=lambda: FIXED_TIME,
            )
            permission_bits = env_file.stat().st_mode & 0o777

        self.assertEqual(permission_bits, ENV_FILE_PERMISSION_MODE)

    def test_obtain_and_persist_accepts_network_and_clock_injection(self) -> None:
        """The combined workflow should remain fully offline in tests."""
        with TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"

            def fake_opener(
                _request: Request,
                *,
                timeout: int,
            ) -> io.BytesIO:
                """Return one deterministic token payload."""
                self.assertEqual(timeout, 7)
                return io.BytesIO(b'{"token": "combined-token"}')

            stored = obtain_and_persist_token(
                _build_config(),
                env_file,
                opener=fake_opener,
                clock=lambda: FIXED_TIME,
                timeout_seconds=7,
            )

            self.assertEqual(stored.access_token, "combined-token")
            self.assertIn(
                "ACLED_BEARER_TOKEN=combined-token",
                env_file.read_text(encoding="utf-8"),
            )
