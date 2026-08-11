"""What the command line says when the server refuses a search.

The server states why it refused: which date is wrong, which source name it
does not know. These tests fix that the reader sees that sentence instead of a
status code followed by the full request address.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from news.cli.fetch import fetch_api_page, server_explanation
from news.cli.output import download_api_export
from news.cli.parser import build_arg_parser

SERVER_URL = "https://news.example.com"


def _json_response(status_code: int, payload: object) -> httpx.Response:
    """Build the response a FastAPI route sends when it refuses a request."""
    return httpx.Response(
        status_code,
        request=httpx.Request("GET", f"{SERVER_URL}/api/search"),
        json=payload,
    )


class ServerExplanationTests(unittest.TestCase):
    """Both refusal shapes the server can send must survive."""

    def test_deliberate_refusal_message_is_repeated(self) -> None:
        """A route that refuses on purpose sends one sentence in "detail"."""
        response = _json_response(
            422, {"detail": "Start date must be on or before end date"}
        )

        self.assertEqual(
            server_explanation(response),
            "Start date must be on or before end date",
        )

    def test_automatic_validation_names_the_parameter(self) -> None:
        """Automatic checks send a list, and the reader needs the field name."""
        response = _json_response(
            422,
            {
                "detail": [
                    {
                        "loc": ["query", "start"],
                        "msg": "Input should be a valid date",
                        "type": "date_parsing",
                    }
                ]
            },
        )

        explanation = server_explanation(response)

        self.assertIn("start", explanation)
        self.assertIn("valid date", explanation)

    def test_two_validation_failures_are_both_reported(self) -> None:
        """Fixing one parameter and rerunning to find the next wastes a call."""
        response = _json_response(
            422,
            {
                "detail": [
                    {"loc": ["query", "start"], "msg": "field required"},
                    {"loc": ["query", "end"], "msg": "field required"},
                ]
            },
        )

        explanation = server_explanation(response)

        self.assertIn("start", explanation)
        self.assertIn("end", explanation)

    def test_body_without_a_reason_explains_nothing(self) -> None:
        """A proxy error page must not be mistaken for a server message."""
        response = httpx.Response(
            502,
            request=httpx.Request("GET", f"{SERVER_URL}/api/search"),
            content=b"<html><body>Bad Gateway</body></html>",
            headers={"content-type": "text/html"},
        )

        self.assertEqual(server_explanation(response), "")

    def test_long_message_is_trimmed(self) -> None:
        """One refusal must not fill the terminal."""
        response = _json_response(400, {"detail": "x" * 5000})

        explanation = server_explanation(response)

        self.assertLess(len(explanation), 400)
        self.assertTrue(explanation.endswith("..."))


class RefusedSearchTests(unittest.TestCase):
    """Both request paths must report the reason, not just the status."""

    def test_search_and_export_both_report_the_reason(self) -> None:
        """The export route is refused for the same reasons as the search."""
        args = build_arg_parser().parse_args(
            [
                "inflation",
                "-s",
                "2025-03-01",
                "-e",
                "2025-01-01",
                "--export",
                "csv",
                "--server",
                SERVER_URL,
            ]
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
                self.assertIn("Start date must be on or before end date", message)
                self.assertIn("422", message)
                # The full request address is long and says nothing about the
                # fix, so it must not replace the server's own sentence.
                self.assertNotIn("newsapi_search_in", message)


class _RefusingClient:
    """Stand-in HTTP client that refuses every request with an explanation."""

    def __init__(self, *_args: object, **_keyword_args: object) -> None:
        pass

    def __enter__(self) -> _RefusingClient:
        return self

    def __exit__(self, *_exception_details: object) -> bool:
        return False

    def get(self, *_args: object, **_keyword_args: object) -> SimpleNamespace:
        """Answer with the refusal the search route sends for a bad window."""
        response = _json_response(
            422, {"detail": "Start date must be on or before end date"}
        )
        return SimpleNamespace(
            status_code=response.status_code,
            is_error=True,
            text=response.text,
            json=response.json,
        )


if __name__ == "__main__":
    unittest.main()
