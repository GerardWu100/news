"""What a failed source request is allowed to write into the log.

Several sources take their key as a query parameter, so an HTTP error carries
the key inside the request address it reports. Nothing here may reach the log
file or the browser response.
"""

from __future__ import annotations

import logging
import unittest
from unittest.mock import patch

import httpx

from news.sources import search_all_detailed
from news.sources.base import (
    Article,
    BaseSource,
    SourcePageResult,
    SourceSearchOptions,
)

SECRET_KEY = "not-a-real-key-2f9c4b7a"
PROVIDER_URL = (
    f"https://api.example.com/search?api-key={SECRET_KEY}&q=inflation"
)
SEARCH_OPTIONS = SourceSearchOptions(
    query="inflation",
    start_date="2025-01-01",
    end_date="2025-01-31",
)


class _FailingSource(BaseSource):
    """Source adapter that always fails the way a rejected key does."""

    name = "gdelt"
    display_name = "Failing Source"
    description = "Fails with an HTTP error carrying a key in its address"

    def is_available(self) -> bool:
        """Report availability so the search actually calls this adapter."""
        return True

    async def search(self, _options: SourceSearchOptions) -> SourcePageResult:
        """Raise the error httpx raises when a provider rejects the key."""
        request = httpx.Request("GET", PROVIDER_URL)
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError(
            f"Client error '401 Unauthorized' for url '{PROVIDER_URL}'",
            request=request,
            response=response,
        )


class _WorkingSource(BaseSource):
    """Source adapter that succeeds, to prove one failure isolates cleanly."""

    name = "nyt"
    display_name = "Working Source"
    description = "Returns one article"

    def is_available(self) -> bool:
        """Report availability so the search actually calls this adapter."""
        return True

    async def search(self, _options: SourceSearchOptions) -> SourcePageResult:
        """Return one normalized article."""
        return SourcePageResult(
            articles=[
                Article(
                    title="Prices rise",
                    url="https://example.com/a",
                    date="2025-01-02",
                    source="nyt",
                )
            ],
            has_more=False,
        )


class FailureLoggingTests(unittest.IsolatedAsyncioTestCase):
    """Verify that a failed source request keeps its credentials to itself."""

    async def test_provider_key_never_reaches_the_log(self) -> None:
        """A key written to a log file outlives the request that leaked it."""
        with patch(
            "news.sources.ALL_SOURCES",
            [_FailingSource(), _WorkingSource()],
        ):
            with self.assertLogs("news.sources", level=logging.DEBUG) as captured:
                articles, reports = await search_all_detailed(SEARCH_OPTIONS)

        logged_text = "\n".join(captured.output)
        self.assertNotIn(SECRET_KEY, logged_text)
        self.assertNotIn("api-key", logged_text)

        # The log still has to be useful: name the source and the status.
        self.assertIn("gdelt", logged_text)
        self.assertIn("401", logged_text)
        self.assertIn("api.example.com", logged_text)

        # One failing source must not remove the other source's results.
        self.assertEqual(len(articles), 1)
        failing_report = next(report for report in reports if report.name == "gdelt")
        self.assertNotIn(SECRET_KEY, failing_report.error)

    async def test_browser_message_names_the_setting_not_the_key(self) -> None:
        """The reader needs to know which key to check, never its value."""
        with patch(
            "news.sources.ALL_SOURCES",
            [_FailingSource()],
        ):
            with self.assertLogs("news.sources", level=logging.DEBUG):
                _articles, reports = await search_all_detailed(SEARCH_OPTIONS)

        self.assertIn("Check the configured key", reports[0].error)


if __name__ == "__main__":
    unittest.main()
