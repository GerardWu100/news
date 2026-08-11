"""Browser-protection headers on every kind of response.

These checks exist because the headers are easy to lose: a route added later
that returns a plain response would silently ship without a Content Security
Policy unless something fails here.
"""

from __future__ import annotations

import unittest
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from news.api.app import create_app
from news.sources import SourceQueryReport
from news.sources.base import Article, SourceSearchOptions
from news.web.config import load_settings
from news.web.security import (
    FONT_FILE_HOST,
    FONT_STYLESHEET_HOST,
    STRICT_TRANSPORT_SECURITY_VALUE,
)
from tests.fixtures.authentication import (
    TEST_PASSWORD,
    TEST_USERNAME,
    basic_auth_headers,
    build_login_sessions,
)
from tests.fixtures.search_results import build_provider_response

# Routes that return account-protected data and must never be stored by a
# shared cache.
DATA_PATHS = (
    "/api/config",
    "/api/sources",
    "/api/search?q=inflation&start=2025-01-01&end=2025-01-02",
    "/api/export/csv?q=inflation&start=2025-01-01&end=2025-01-02",
    "/api/export/json?q=inflation&start=2025-01-01&end=2025-01-02",
)


async def _offline_search_executor(
    _options: SourceSearchOptions,
    _source_names: Sequence[str] | None,
) -> tuple[list[Article], list[SourceQueryReport]]:
    """Return one offline provider page instead of calling the network."""
    return build_provider_response()


class SecurityHeaderTestCase(unittest.TestCase):
    """Shared setup: one application with a temporary account."""

    def setUp(self) -> None:
        """Build an application whose account lives in a temporary directory."""
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.data_directory = Path(temporary_directory.name)
        self.application = create_app(
            load_settings(),
            search_executor=_offline_search_executor,
            login_sessions=build_login_sessions(self.data_directory),
        )
        self.client = TestClient(self.application)
        self.account_headers = basic_auth_headers(TEST_USERNAME, TEST_PASSWORD)


class DataResponseHeaderTests(SecurityHeaderTestCase):
    """Verify the headers on responses that carry search results."""

    def test_data_routes_block_framing_sniffing_and_storage(self) -> None:
        """Search results must not be framed, sniffed, or written to a cache."""
        for path in DATA_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.account_headers)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                self.assertEqual(
                    response.headers["X-Content-Type-Options"],
                    "nosniff",
                )
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                self.assertIn(
                    "default-src 'none'",
                    response.headers["Content-Security-Policy"],
                )

    def test_refused_requests_are_protected_too(self) -> None:
        """A 401 is still a response a browser renders."""
        response = self.client.get("/api/search?q=x&start=2025-01-01&end=2025-01-02")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn(
            "default-src 'none'",
            response.headers["Content-Security-Policy"],
        )


class SearchPageHeaderTests(SecurityHeaderTestCase):
    """Verify the wider policy the browser search page needs."""

    def test_search_page_allows_only_its_own_code_and_the_web_fonts(self) -> None:
        """The page must load its scripts and fonts without allowing more."""
        response = self.client.get("/", headers=self.account_headers)
        policy = response.headers["Content-Security-Policy"]

        self.assertEqual(response.status_code, 200)
        self.assertIn("script-src 'self'", policy)
        self.assertIn(f"style-src 'self' {FONT_STYLESHEET_HOST}", policy)
        self.assertIn(f"font-src {FONT_FILE_HOST}", policy)
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_search_page_forbids_inline_scripts_and_styles(self) -> None:
        """Injected markup must have no way to execute or restyle the page."""
        policy = self.client.get("/", headers=self.account_headers).headers[
            "Content-Security-Policy"
        ]

        self.assertNotIn("unsafe-inline", policy)
        self.assertNotIn("unsafe-eval", policy)


class DocumentationPageHeaderTests(SecurityHeaderTestCase):
    """Verify the narrower policy the documentation page needs."""

    def test_documentation_page_loads_styles_and_fonts_but_runs_nothing(self) -> None:
        """The page is plain markup, so it has no reason to run a script."""
        response = self.client.get("/docs", headers=self.account_headers)
        policy = response.headers["Content-Security-Policy"]

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"style-src 'self' {FONT_STYLESHEET_HOST}", policy)
        self.assertIn(f"font-src {FONT_FILE_HOST}", policy)
        self.assertNotIn("script-src", policy)
        self.assertNotIn("unsafe-inline", policy)

    def test_documentation_page_needs_an_account(self) -> None:
        """It names this deployment's routes, sources, and options."""
        response = self.client.get("/docs", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "/login")


class StaticAssetHeaderTests(SecurityHeaderTestCase):
    """Verify that package-owned files may be stored but must be revalidated."""

    def test_static_files_are_stored_but_never_reused_unchecked(self) -> None:
        """A cache holding an old stylesheet makes a new page look broken.

        The page markup is never cached, so an intermediate cache that keeps
        yesterday's stylesheet pairs today's markup with styles that do not
        describe it. ``no-cache`` still stores the file; it only requires a
        check before reuse, which an unchanged file answers with a 304.
        """
        response = self.client.get("/static/favicon.svg")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["Cache-Control"], "no-cache")
        self.assertNotIn("no-store", response.headers["Cache-Control"])


class StrictTransportSecurityTests(SecurityHeaderTestCase):
    """Verify when the browser is told to insist on HTTPS."""

    def test_plain_connections_are_not_told_to_insist_on_https(self) -> None:
        """Promising HTTPS over plain HTTP locks a local deployment out."""
        response = self.client.get("/healthz")

        self.assertNotIn("Strict-Transport-Security", response.headers)

    def test_https_connections_are_told_to_insist_on_https(self) -> None:
        """Once a browser has arrived securely, it should not drop back."""
        secure_client = TestClient(self.application, base_url="https://testserver")
        response = secure_client.get("/healthz")

        self.assertEqual(
            response.headers["Strict-Transport-Security"],
            STRICT_TRANSPORT_SECURITY_VALUE,
        )


if __name__ == "__main__":
    unittest.main()
