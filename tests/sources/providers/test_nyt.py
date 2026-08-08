"""Tests for New York Times response normalization."""

from __future__ import annotations

import unittest

import httpx
from news.sources.base import SourceSearchOptions
from news.sources.providers.nyt import (
    DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
    NewYorkTimesSource,
)


class NewYorkTimesNormalizationTests(unittest.TestCase):
    """Check New York Times normalization into the shared article model."""

    def test_nyt_to_article_normalizes_expected_fields(self) -> None:
        """New York Times results should map into the unified schema."""
        article = NewYorkTimesSource._to_article(
            {
                "headline": {"main": "Fed weighs next move"},
                "web_url": "https://www.nytimes.com/2026/03/05/business/fed.html",
                "pub_date": "2026-03-05T09:30:00+0000",
                "language": "en",
                "abstract": "The Fed is considering the next step.",
                "snippet": "Officials remain cautious.",
                "section_name": "Business",
                "byline": {"original": "By Jane Doe"},
            }
        )

        self.assertEqual(article.title, "Fed weighs next move")
        self.assertEqual(article.date, "2026-03-05")
        self.assertEqual(article.source, "nyt")
        self.assertEqual(article.domain, "nytimes.com")
        self.assertEqual(article.language, "en")
        self.assertEqual(article.summary, "The Fed is considering the next step.")
        self.assertEqual(article.content, "Officials remain cautious.")
        self.assertEqual(article.section, "Business")
        self.assertEqual(article.author, "By Jane Doe")


class NewYorkTimesCooldownTests(unittest.IsolatedAsyncioTestCase):
    """Check New York Times rate-limit behavior."""

    async def test_nyt_search_respects_local_cooldown(self) -> None:
        """A recent HTTP 429 should block immediate follow-up requests."""
        source = NewYorkTimesSource()
        throttled_response = httpx.Response(
            429,
            headers={"Retry-After": "5"},
            request=httpx.Request("GET", source._BASE_URL),
        )
        source._cooldown.activate_from_response(
            throttled_response,
            default_seconds=DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
        )

        with self.assertRaises(RuntimeError) as context:
            await source.search(
                SourceSearchOptions(
                    query="Trump",
                    start_date="2026-02-03",
                    end_date="2026-03-06",
                )
            )

        self.assertIn("Try again in", str(context.exception))
