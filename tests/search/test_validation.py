"""Tests for search-request validation and boundary normalization."""

from __future__ import annotations

import unittest

from news.search import build_search_request
from news.search.errors import SearchValidationError
from news.search.validation import split_csv_values


class BuildSearchRequestTests(unittest.TestCase):
    """Validate request normalization and error handling."""

    def test_source_registry_lists_known_provider_names(self) -> None:
        """Validation should use the explicit source registry lookup."""
        from news.sources.registry import source_names

        self.assertIn("gdelt", source_names())
        self.assertIn("guardian", source_names())

    def test_empty_source_list_stays_explicit(self) -> None:
        """Delimiter-only source input should not broaden the search."""
        request = build_search_request(
            query="inflation",
            start_date="2026-02-01",
            end_date="2026-02-10",
            source_names=split_csv_values(","),
            language="",
            deduplicate=True,
        )

        self.assertEqual(request.source_names, ())
        self.assertIsNotNone(request.source_names)

    def test_rejects_invalid_newsapi_search_scope(self) -> None:
        """Unknown NewsAPI field scopes should fail instead of broadening search."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2026-02-01",
                end_date="2026-02-10",
                source_names=None,
                language="",
                deduplicate=True,
                newsapi_search_in="banana",
            )

        self.assertIn("newsapi_search_in", context.exception.message)

    def test_rejects_reverse_date_range(self) -> None:
        """Start dates after end dates should raise a 422 error."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query=" inflation ",
                start_date="2026-02-10",
                end_date="2026-02-01",
                source_names=None,
                language="EN",
                deduplicate=True,
            )

        self.assertIn("Start date", context.exception.message)

    def test_rejects_unknown_source(self) -> None:
        """Unregistered source names should fail fast."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2026-02-01",
                end_date="2026-02-10",
                source_names=["gdelt", "unknown-source"],
                language="",
                deduplicate=True,
            )

        self.assertIn("unknown-source", context.exception.message)

    def test_rejects_invalid_match_mode(self) -> None:
        """Unsupported advanced search options should fail validation."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2026-02-01",
                end_date="2026-02-10",
                source_names=None,
                language="",
                deduplicate=True,
                match_mode="impossible",
            )

        self.assertIn("match_mode", context.exception.message)

    def test_rejects_invalid_date_format(self) -> None:
        """Dates must use strict ISO calendar form."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2026-2-01",
                end_date="2026-02-10",
                source_names=None,
                language="",
                deduplicate=True,
            )

        self.assertIn("start", context.exception.message)

    def test_rejects_overlong_date_range(self) -> None:
        """Large backfills should be split into smaller windows."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2025-01-01",
                end_date="2026-02-10",
                source_names=None,
                language="",
                deduplicate=True,
            )

        self.assertIn("366 days", context.exception.message)

    def test_inclusive_date_limit_accepts_366_dates_and_rejects_367(self) -> None:
        """The limit counts both publication-date boundaries."""
        accepted = build_search_request(
            query="inflation",
            start_date="2024-01-02",
            end_date="2025-01-01",
            source_names=None,
            language="",
            deduplicate=True,
        )
        self.assertEqual(accepted.end_date, "2025-01-01")

        with self.assertRaises(SearchValidationError):
            build_search_request(
                query="inflation",
                start_date="2024-01-01",
                end_date="2025-01-01",
                source_names=None,
                language="",
                deduplicate=True,
            )

    def test_parses_provider_aware_advanced_filters(self) -> None:
        """Comma-separated advanced fields should normalize into tuples."""
        request = build_search_request(
            query="rates",
            start_date="2026-02-01",
            end_date="2026-02-10",
            source_names=("guardian", "nyt", "newsapi"),
            language="en",
            deduplicate=True,
            domain_filter="reuters.com, wsj.com",
            exclude_domains="reddit.com\nyoutube.com",
            provider_sort="relevance",
            section="business, world",
            news_desk="Business Day, Washington",
            guardian_tag="business/economics",
            newsapi_search_in="description,title",
        )

        self.assertEqual(request.include_domains, ("reuters.com", "wsj.com"))
        self.assertEqual(request.exclude_domains, ("reddit.com", "youtube.com"))
        self.assertEqual(request.provider_sort, "relevance")
        self.assertEqual(request.section_filters, ("business", "world"))
        self.assertEqual(request.news_desk_filters, ("Business Day", "Washington"))
        self.assertEqual(request.guardian_tags, ("business/economics",))
        self.assertEqual(request.newsapi_search_in, "title,description")
