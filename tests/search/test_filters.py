"""Tests for local language filtering and stable result sorting."""

from __future__ import annotations

import unittest

from news.search.filters import filter_by_language, sort_articles
from news.sources.base import Article


class FilterBehaviorTests(unittest.TestCase):
    """Check local filter behavior that can quietly distort research output."""

    def test_language_filter_does_not_match_french_when_requesting_english(
        self,
    ) -> None:
        """The English shortcut should not keep French-language rows."""
        articles = [
            Article(
                title="French story",
                url="https://example.com/fr",
                date="2026-01-01",
                source="test",
                language="french",
            ),
            Article(
                title="English story",
                url="https://example.com/en",
                date="2026-01-01",
                source="test",
                language="english",
            ),
            Article(
                title="ISO English story",
                url="https://example.com/iso",
                date="2026-01-01",
                source="test",
                language="en",
            ),
            Article(
                title="Unknown language story",
                url="https://example.com/unknown",
                date="2026-01-01",
                source="test",
                language="",
            ),
        ]

        filtered = filter_by_language(articles, "en")

        self.assertEqual(
            [article.title for article in filtered],
            ["English story", "ISO English story", "Unknown language story"],
        )

    def test_language_filter_normalizes_common_provider_labels(self) -> None:
        """Language filtering should accept common tags without substring leaks."""
        articles = [
            Article(
                title="Regional English story",
                url="https://example.com/en-us",
                date="2026-01-01",
                source="test",
                language="en-US",
            ),
            Article(
                title="Whitespace English story",
                url="https://example.com/english",
                date="2026-01-01",
                source="test",
                language=" English ",
            ),
            Article(
                title="French story",
                url="https://example.com/french",
                date="2026-01-01",
                source="test",
                language="french",
            ),
        ]

        filtered = filter_by_language(articles, "en")

        self.assertEqual(
            [article.title for article in filtered],
            ["Regional English story", "Whitespace English story"],
        )

    def test_language_filter_supports_spanish_name_alias(self) -> None:
        """Spanish requests should match provider labels that spell the language."""
        articles = [
            Article(
                title="Spanish story",
                url="https://example.com/spanish",
                date="2026-01-01",
                source="test",
                language="spanish",
            ),
            Article(
                title="English story",
                url="https://example.com/english",
                date="2026-01-01",
                source="test",
                language="english",
            ),
        ]

        filtered = filter_by_language(articles, "es")

        self.assertEqual([article.title for article in filtered], ["Spanish story"])

    def test_date_desc_sort_keeps_title_ascending_inside_same_date(self) -> None:
        """Date descending should not reverse alphabetical title ties."""
        articles = [
            Article(
                title="Zulu",
                url="https://example.com/z",
                date="2026-01-01",
                source="test",
            ),
            Article(
                title="Alpha",
                url="https://example.com/a",
                date="2026-01-01",
                source="test",
            ),
            Article(
                title="Beta",
                url="https://example.com/b",
                date="2026-01-02",
                source="test",
            ),
        ]

        sorted_articles = sort_articles(articles, "date_desc")

        self.assertEqual(
            [article.title for article in sorted_articles],
            ["Beta", "Alpha", "Zulu"],
        )
