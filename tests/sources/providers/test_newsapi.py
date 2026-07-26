"""Tests for NewsAPI request parameters and response normalization."""

from __future__ import annotations

import unittest

from news.sources.base import SourceSearchOptions
from news.sources.providers.newsapi import _build_params as build_newsapi_params
from news.sources.providers.newsapi import _to_article as newsapi_to_article


class NewsApiNormalizationTests(unittest.TestCase):
    """Check NewsAPI request and normalization contracts."""

    def test_newsapi_helpers_build_expected_request_and_article(self) -> None:
        """NewsAPI parameters and records should follow the shared model."""
        params = build_newsapi_params(
            options=SourceSearchOptions(
                query="fed",
                start_date="2026-03-01",
                end_date="2026-03-05",
                page=2,
                language="en",
                provider_sort="popularity",
                include_domains=("reuters.com", "wsj.com"),
                exclude_domains=("reddit.com",),
                newsapi_search_in="title,description",
            ),
        )
        article = newsapi_to_article(
            {
                "title": "Fed minutes signal patience",
                "url": "https://www.reuters.com/world/us/fed-minutes-2026-03-05/",
                "publishedAt": "2026-03-05T18:30:00Z",
                "description": "Officials are not rushing.",
                "content": "Longer text here. [+123 chars]",
                "author": "John Smith",
                "source": {"name": "Reuters"},
            },
            requested_language="en",
        )

        self.assertEqual(params["sortBy"], "popularity")
        self.assertEqual(params["searchIn"], "title,description")
        self.assertEqual(params["domains"], "reuters.com,wsj.com")
        self.assertEqual(params["excludeDomains"], "reddit.com")
        self.assertEqual(params["page"], "2")
        self.assertEqual(article.title, "Fed minutes signal patience")
        self.assertEqual(article.date, "2026-03-05")
        self.assertEqual(article.domain, "reuters.com")
        self.assertEqual(article.language, "en")
        self.assertEqual(article.summary, "Officials are not rushing.")
        self.assertEqual(article.content, "Longer text here.")
        self.assertEqual(article.section, "Reuters")
        self.assertEqual(article.author, "John Smith")
