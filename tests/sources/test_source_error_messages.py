"""What a failed source request tells the reader.

A status number alone does not say what to change. Providers explain refusals
in the response body: NewsAPI names the earliest date the plan allows and
MediaCloud names the parameter it wanted. These tests fix that behavior, and
fix the limits on it, since the same body could repeat a key.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx

from news.sources import _format_source_error, _redacted_failure_detail

PROVIDER_URL = "https://api.example.com/search"


def _status_error(
    status_code: int,
    body: str,
    content_type: str = "application/json",
) -> httpx.HTTPStatusError:
    """Build the error httpx raises when a provider rejects a request."""
    request = httpx.Request("GET", PROVIDER_URL)
    response = httpx.Response(
        status_code,
        request=request,
        content=body.encode("utf-8"),
        headers={"content-type": content_type},
    )
    return httpx.HTTPStatusError("rejected", request=request, response=response)


class ProviderExplanationTests(unittest.TestCase):
    """The provider's own words should survive into the source report."""

    def test_newsapi_plan_limit_is_repeated(self) -> None:
        """HTTP 426 alone hides the one fact that matters: the date floor."""
        body = (
            '{"status":"error","code":"parameterInvalid","message":'
            '"You are trying to request results too far in the past. '
            'Your plan permits you to request articles as far back as 2026-07-10."}'
        )
        message = _format_source_error(_status_error(426, body))

        self.assertIn("HTTP 426", message)
        self.assertIn("as far back as 2026-07-10", message)

    def test_mediacloud_note_field_is_repeated(self) -> None:
        """MediaCloud explains itself in "note" rather than "message"."""
        body = '{"status":"error","note":"Must have at least one of \'ss\' or \'cs\'"}'
        message = _format_source_error(_status_error(422, body))

        self.assertIn("'ss' or 'cs'", message)

    def test_plain_text_refusal_is_repeated(self) -> None:
        """GDELT answers rate limits as plain text with no structure at all."""
        message = _format_source_error(
            _status_error(
                429,
                "Please limit requests to one every 5 seconds.",
                content_type="text/plain",
            )
        )

        self.assertIn("rate limited", message)
        self.assertIn("one every 5 seconds", message)

    def test_html_error_page_is_left_out(self) -> None:
        """Markup would fill the report without explaining anything."""
        message = _format_source_error(
            _status_error(
                503,
                "<html><body><h1>502 Bad Gateway</h1></body></html>",
                content_type="text/html",
            )
        )

        self.assertNotIn("<html>", message)
        self.assertIn("Source server error", message)

    def test_empty_body_leaves_the_summary_alone(self) -> None:
        """With nothing to add, the message stays the plain summary."""
        message = _format_source_error(_status_error(404, ""))

        self.assertEqual(message, "Source request failed with HTTP 404.")

    def test_long_message_is_trimmed(self) -> None:
        """One provider must not be able to flood the report."""
        body = '{"message":"' + ("x" * 5000) + '"}'
        message = _format_source_error(_status_error(400, body))

        self.assertLess(len(message), 400)
        self.assertTrue(message.endswith("..."))


class CredentialRedactionTests(unittest.TestCase):
    """A provider that quotes the request back must not publish the key."""

    def test_configured_key_is_removed_from_the_message(self) -> None:
        """The reader needs the reason, never the secret that was rejected."""
        secret = "not-a-real-key-2f9c4b7a"
        body = f'{{"message":"Invalid key {secret} for this endpoint"}}'

        with patch.dict("os.environ", {"NEWSAPI_API_KEY": secret}, clear=False):
            message = _format_source_error(_status_error(401, body))

        self.assertNotIn(secret, message)
        self.assertIn("<NEWSAPI_API_KEY>", message)

    def test_short_secret_is_left_in_place(self) -> None:
        """Blanking a two-character value would erase ordinary words."""
        body = '{"message":"Rejected because the account is over quota"}'

        with patch.dict("os.environ", {"NEWSAPI_API_KEY": "ac"}, clear=False):
            message = _format_source_error(_status_error(401, body))

        self.assertIn("over quota", message)


class TimeoutMessageTests(unittest.TestCase):
    """Connect and read timeouts have different causes and different fixes."""

    def test_connect_timeout_names_the_connect_setting(self) -> None:
        """A handshake that never finished is not a slow answer."""
        message = _format_source_error(httpx.ConnectTimeout("too slow"))

        self.assertIn("open a connection", message)
        self.assertIn("connect_timeout_seconds", message)

    def test_read_timeout_names_the_read_setting(self) -> None:
        """The connection worked; the response did not arrive."""
        message = _format_source_error(httpx.ReadTimeout("too slow"))

        self.assertIn("did not answer in time", message)
        self.assertIn("read_timeout_seconds", message)


class LogDetailTests(unittest.TestCase):
    """The log must keep the provider status even when the message is replaced."""

    def test_status_survives_an_adapter_specific_message(self) -> None:
        """Adapters raise RuntimeError from the original error; follow it."""
        original = _status_error(401, "")
        try:
            raise RuntimeError("Token refused") from original
        except RuntimeError as replaced:
            detail = _redacted_failure_detail(replaced)

        self.assertIn("HTTP 401", detail)
        self.assertIn("api.example.com", detail)

    def test_error_without_a_request_says_so(self) -> None:
        """A failure that never reached the network has no address to log."""
        self.assertEqual(
            _redacted_failure_detail(RuntimeError("no collections configured")),
            "no request details",
        )


if __name__ == "__main__":
    unittest.main()
