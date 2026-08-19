"""Offline contract tests for the ACLED provider adapter."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import httpx

from news.sources.base import SourceSearchOptions
from news.sources.providers.acled import AcledSource


class AcledSourceTests(unittest.IsolatedAsyncioTestCase):
    """Verify availability, pagination, and event normalization."""

    def test_availability_requires_bearer_token(self) -> None:
        """The adapter should be available only with a nonblank token."""
        source = AcledSource()

        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(source.is_available())
        with patch.dict("os.environ", {"ACLED_BEARER_TOKEN": "token"}, clear=True):
            self.assertTrue(source.is_available())

    async def test_pages_after_first_return_without_network_access(self) -> None:
        """ACLED should expose its documented single-page behavior offline."""
        result = await AcledSource().search(
            SourceSearchOptions(
                query="protest",
                start_date="2026-07-01",
                end_date="2026-07-10",
                page=2,
            )
        )

        self.assertEqual(result.articles, [])
        self.assertFalse(result.has_more)

    async def test_full_single_page_does_not_advertise_unreachable_page_two(
        self,
    ) -> None:
        """A capped first page is still final until pagination is implemented."""
        response = httpx.Response(
            200,
            json={"data": [{} for _row in range(50)]},
            request=httpx.Request("GET", "https://example.test"),
        )
        with (
            patch.dict("os.environ", {"ACLED_BEARER_TOKEN": "token"}),
            patch(
                "news.sources.providers.acled.get_with_retry",
                new=AsyncMock(return_value=response),
            ),
        ):
            result = await AcledSource().search(
                SourceSearchOptions(
                    query="protest",
                    start_date="2026-07-01",
                    end_date="2026-07-10",
                )
            )

        self.assertEqual(len(result.articles), 50)
        self.assertFalse(result.has_more)

    def test_event_normalization_uses_shared_article_fields(self) -> None:
        """One conflict event should map into the common article schema."""
        article = AcledSource._to_article(
            {
                "event_type": "Protests",
                "notes": "Workers gathered outside parliament.",
                "source_url": "https://example.com/event",
                "event_date": "2026-07-09",
                "source": "Example News",
            }
        )

        self.assertEqual(
            article.title,
            "[Protests] Workers gathered outside parliament.",
        )
        self.assertEqual(article.url, "https://example.com/event")
        self.assertEqual(article.date, "2026-07-09")
        self.assertEqual(article.source, "acled")
        self.assertEqual(article.domain, "Example News")
