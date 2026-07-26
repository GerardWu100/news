"""Regression tests for CLI argument parsing and display helpers."""

from __future__ import annotations

import unittest

from news.cli.output import format_table
from news.cli.parser import build_api_params, build_arg_parser


class ArgParserTests(unittest.TestCase):
    """Test CLI argument parsing and defaults."""

    def test_minimal_args(self) -> None:
        """The parser should accept the smallest valid invocation."""
        parser = build_arg_parser()
        args = parser.parse_args(["inflation", "-s", "2025-01-01", "-e", "2025-03-01"])

        self.assertEqual(args.query, "inflation")
        self.assertEqual(args.start, "2025-01-01")
        self.assertEqual(args.end, "2025-03-01")
        self.assertFalse(args.json)
        self.assertFalse(args.direct)
        self.assertEqual(args.page, 1)

    def test_all_flags(self) -> None:
        """The parser should expose every supported CLI option."""
        parser = build_arg_parser()
        args = parser.parse_args(
            [
                "fed rates",
                "-s",
                "2025-01-01",
                "-e",
                "2025-03-01",
                "--sources",
                "guardian,nyt",
                "--english",
                "--no-dedupe",
                "--exact-phrase",
                "federal reserve",
                "--exclude",
                "sports",
                "--domain",
                "reuters.com",
                "--exclude-domains",
                "reddit.com",
                "--scope",
                "title",
                "--match",
                "all_terms",
                "--sort",
                "date_asc",
                "--provider-sort",
                "relevance",
                "--section",
                "business",
                "--news-desk",
                "Business Day",
                "--guardian-tag",
                "business/economics",
                "--newsapi-search-in",
                "title",
                "--page",
                "3",
                "--json",
                "--export",
                "sqlite",
                "--output",
                "news.db",
                "--include-content",
                "--all-pages",
                "--max-pages",
                "10",
                "--server",
                "http://remote:8000",
                "-q",
            ]
        )

        self.assertEqual(args.query, "fed rates")
        self.assertEqual(args.sources, "guardian,nyt")
        self.assertTrue(args.english)
        self.assertTrue(args.no_dedupe)
        self.assertEqual(args.exact_phrase, "federal reserve")
        self.assertEqual(args.exclude, "sports")
        self.assertEqual(args.scope, "title")
        self.assertEqual(args.match, "all_terms")
        self.assertEqual(args.sort, "date_asc")
        self.assertTrue(args.json)
        self.assertEqual(args.export, "sqlite")
        self.assertEqual(args.output, "news.db")
        self.assertTrue(args.include_content)
        self.assertTrue(args.all_pages)
        self.assertEqual(args.max_pages, 10)
        self.assertEqual(args.server, "http://remote:8000")
        self.assertTrue(args.quiet)


class BuildApiParamsTests(unittest.TestCase):
    """Test mapping CLI args to API query parameters."""

    def test_maps_english_flag_to_language(self) -> None:
        """The convenience English flag should override language."""
        parser = build_arg_parser()
        args = parser.parse_args(
            ["fed", "-s", "2025-01-01", "-e", "2025-03-01", "--english"]
        )
        params = build_api_params(args)

        self.assertEqual(params["language"], "en")

    def test_maps_no_dedupe_to_false(self) -> None:
        """The negated dedupe flag should map to the API boolean string."""
        parser = build_arg_parser()
        args = parser.parse_args(
            ["fed", "-s", "2025-01-01", "-e", "2025-03-01", "--no-dedupe"]
        )
        params = build_api_params(args)

        self.assertEqual(params["dedupe"], "false")


class TableFormatTests(unittest.TestCase):
    """Test table output rendering."""

    def test_format_table_renders_rows(self) -> None:
        """The default table renderer should include key row fields."""
        articles = [
            {
                "title": "Fed holds rates",
                "url": "https://example.com/fed",
                "date": "2025-03-01",
                "source": "guardian",
                "domain": "example.com",
            }
        ]
        meta = {
            "query": "fed",
            "start": "2025-01-01",
            "end": "2025-03-01",
            "requested_sources": ["guardian"],
            "returned": 1,
            "duplicates_removed": 0,
            "page": 1,
            "has_more": False,
        }

        output = format_table(articles, meta)

        self.assertIn("Fed holds rates", output)
        self.assertIn("guardian", output)
        self.assertIn("2025-03-01", output)


class PackageEntryPointTests(unittest.TestCase):
    """Check that package entry points are available through project metadata."""

    def test_pyproject_defines_news_scripts(self) -> None:
        """The project should expose canonical server and CLI commands."""
        import tomllib
        from pathlib import Path

        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with pyproject_path.open("rb") as pyproject_file:
            pyproject = tomllib.load(pyproject_file)

        scripts = pyproject["project"]["scripts"]

        self.assertEqual(scripts["news-server"], "news.api.app:main")
        self.assertEqual(scripts["news-search"], "news.cli.workflow:main")


if __name__ == "__main__":
    unittest.main()
