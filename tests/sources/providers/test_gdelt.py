"""Offline contract tests for the GDELT provider adapter."""

from __future__ import annotations

import unittest

from news.sources.base import SourceSearchOptions
from news.sources.providers.gdelt import GdeltSource, _format_gdelt_date


class GdeltSourceTests(unittest.IsolatedAsyncioTestCase):
    """Verify availability, pagination, dates, and article normalization."""

    def test_source_is_available_without_credentials(self) -> None:
        """GDELT should remain the credential-free default provider."""
        self.assertTrue(GdeltSource().is_available())

    async def test_pages_after_first_return_without_network_access(self) -> None:
        """GDELT should expose its documented single-page behavior offline."""
        result = await GdeltSource().search(
            SourceSearchOptions(
                query="inflation",
                start_date="2026-07-01",
                end_date="2026-07-10",
                page=2,
            )
        )

        self.assertEqual(result.articles, [])
        self.assertFalse(result.has_more)

    def test_compact_timestamp_is_normalized_to_iso_date(self) -> None:
        """GDELT timestamps should use the shared ISO calendar representation."""
        self.assertEqual(_format_gdelt_date("20260709153000"), "2026-07-09")
        self.assertEqual(_format_gdelt_date("202607"), "")

    def test_article_normalization_uses_shared_fields(self) -> None:
        """One document result should map into the common article schema."""
        article = GdeltSource._to_article(
            {
                "title": "Central bank holds rates",
                "url": "https://example.com/rates",
                "seendate": "20260709153000",
                "domain": "example.com",
                "language": "English",
            }
        )

        self.assertEqual(article.title, "Central bank holds rates")
        self.assertEqual(article.url, "https://example.com/rates")
        self.assertEqual(article.date, "2026-07-09")
        self.assertEqual(article.source, "gdelt")
        self.assertEqual(article.domain, "example.com")
        self.assertEqual(article.language, "English")
