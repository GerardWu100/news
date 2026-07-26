"""Tests for Guardian response normalization."""

from __future__ import annotations

import unittest

from news.sources.providers.guardian import GuardianSource


class GuardianNormalizationTests(unittest.TestCase):
    """Check Guardian normalization into the shared article model."""

    def test_guardian_to_article_normalizes_expected_fields(self) -> None:
        """Guardian search results should map cleanly into the unified schema."""
        article = GuardianSource._to_article(
            {
                "webTitle": "UK markets brace for rate decision",
                "webUrl": "https://www.theguardian.com/business/2026/mar/05/rates",
                "webPublicationDate": "2026-03-05T14:22:11Z",
                "sectionName": "Business",
                "fields": {
                    "lang": "en",
                    "trailText": "<p>Markets are waiting for the vote.</p>",
                    "body": "<p>Paragraph one.</p><p>Paragraph two.</p>",
                    "byline": "Jane Doe",
                },
            }
        )

        self.assertEqual(article.title, "UK markets brace for rate decision")
        self.assertEqual(article.date, "2026-03-05")
        self.assertEqual(article.source, "guardian")
        self.assertEqual(article.domain, "theguardian.com")
        self.assertEqual(article.language, "en")
        self.assertEqual(article.summary, "Markets are waiting for the vote.")
        self.assertEqual(article.content, "Paragraph one. Paragraph two.")
        self.assertEqual(article.section, "Business")
        self.assertEqual(article.author, "Jane Doe")
