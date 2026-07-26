"""Tests for explicit package-level public import surfaces."""

from __future__ import annotations

import unittest

import news
import news.api
import news.cli
import news.exports
import news.search
import news.sources
import news.web


class PublicExportTests(unittest.TestCase):
    """Protect intentional package exports from accidental expansion."""

    def test_internal_boundary_packages_export_nothing_implicitly(self) -> None:
        """Root, API, CLI, and web callers should use explicit module paths."""
        self.assertEqual(news.__all__, [])
        self.assertEqual(news.api.__all__, [])
        self.assertEqual(news.cli.__all__, [])
        self.assertEqual(news.web.__all__, [])

    def test_domain_packages_have_explicit_public_objects(self) -> None:
        """Search, source, and export packages should list supported imports."""
        self.assertEqual(
            set(news.search.__all__),
            {
                "SearchExecutor",
                "SearchRequest",
                "SearchResult",
                "build_search_request",
                "canonicalize_url",
                "deduplicate_articles",
                "run_search",
            },
        )
        self.assertEqual(
            set(news.sources.__all__),
            {
                "Article",
                "BaseSource",
                "SourcePageResult",
                "SourceQueryReport",
                "SourceSearchOptions",
                "get_source_status",
                "search_all_detailed",
            },
        )
        self.assertEqual(
            set(news.exports.__all__),
            {"format_csv", "format_json", "write_sqlite"},
        )


if __name__ == "__main__":
    unittest.main()
