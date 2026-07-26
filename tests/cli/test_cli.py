"""Regression tests for CLI argument parsing and display helpers."""

from __future__ import annotations

import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import tomllib

from news.cli.output import format_table
from news.cli.parser import build_api_params, build_arg_parser
from news.cli.workflow import collect_all_pages, run_cli


class ArgParserTests(unittest.TestCase):
    """Test CLI argument parsing and defaults."""

    def test_minimal_args(self) -> None:
        """The parser should accept the smallest valid invocation."""
        parser = build_arg_parser()
        args = parser.parse_args(["inflation", "-s", "2025-01-01", "-e", "2025-03-01"])

        self.assertEqual(args.query, "inflation")
        self.assertEqual(args.start, "2025-01-01")
        self.assertEqual(args.end, "2025-03-01")
        self.assertEqual(args.output_format, "table")
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
        self.assertEqual(args.output_format, "json")
        self.assertEqual(args.export, "sqlite")
        self.assertEqual(args.output, "news.db")
        self.assertTrue(args.include_content)
        self.assertTrue(args.all_pages)
        self.assertEqual(args.max_pages, 10)
        self.assertEqual(args.server, "http://remote:8000")
        self.assertTrue(args.quiet)

    def test_jsonl_format_is_available_for_streaming_consumers(self) -> None:
        """The CLI should expose one-record-per-line structured output."""
        parser = build_arg_parser()

        args = parser.parse_args(
            [
                "earnings",
                "-s",
                "2025-01-01",
                "-e",
                "2025-01-31",
                "--format",
                "jsonl",
            ]
        )

        self.assertEqual(args.output_format, "jsonl")

    def test_help_explains_the_inclusive_information_boundary(self) -> None:
        """CLI help should make the temporal research contract explicit."""
        help_text = build_arg_parser().format_help()

        self.assertIn("inclusive publication end date", help_text.lower())
        self.assertIn("large language model", help_text.lower())


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


class StructuredOutputTests(unittest.TestCase):
    """Test standard-output representations intended for programs."""

    def test_jsonl_emits_one_compact_article_per_line(self) -> None:
        """JSONL should contain article records without a table or metadata row."""
        parser = build_arg_parser()
        args = parser.parse_args(
            [
                "fed",
                "-s",
                "2025-01-01",
                "-e",
                "2025-03-01",
                "--format",
                "jsonl",
            ]
        )
        payload = {
            "results": [
                {"title": "First", "date": "2025-01-01"},
                {"title": "Second", "date": "2025-01-02"},
            ],
            "meta": {},
        }
        output = StringIO()

        with (
            patch("news.cli.workflow.collect_results", return_value=payload),
            redirect_stdout(output),
        ):
            run_cli(args)

        self.assertEqual(
            output.getvalue().splitlines(),
            [
                '{"title":"First","date":"2025-01-01"}',
                '{"title":"Second","date":"2025-01-02"}',
            ],
        )


class PaginatedCollectionTests(unittest.TestCase):
    """Check command-line aggregation across provider pages."""

    def test_collect_all_pages_combines_results_and_metadata(self) -> None:
        """Aggregation should retain rows and sum duplicate-removal counts."""
        args = build_arg_parser().parse_args(
            [
                "fed",
                "-s",
                "2025-01-01",
                "-e",
                "2025-03-01",
                "--all-pages",
                "--quiet",
            ]
        )
        page_payloads = [
            {
                "results": [{"title": "First"}],
                "meta": {"duplicates_removed": 1, "has_more": True},
            },
            {
                "results": [{"title": "Second"}],
                "meta": {"duplicates_removed": 2, "has_more": False},
            },
        ]

        # The backend metadata controls termination; the CLI only aggregates
        # page rows and the duplicate count.
        with patch("news.cli.workflow.fetch_page", side_effect=page_payloads) as fetch:
            payload = collect_all_pages(args)

        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(payload["results"], [{"title": "First"}, {"title": "Second"}])
        self.assertEqual(payload["meta"]["returned"], 2)
        self.assertEqual(payload["meta"]["duplicates_removed"], 3)
        self.assertFalse(payload["meta"]["has_more"])


class PackageEntryPointTests(unittest.TestCase):
    """Check that package entry points are available through project metadata."""

    def test_pyproject_defines_news_scripts(self) -> None:
        """The project should expose canonical server and CLI commands."""
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        with pyproject_path.open("rb") as pyproject_file:
            pyproject = tomllib.load(pyproject_file)

        scripts = pyproject["project"]["scripts"]

        self.assertEqual(scripts["news-server"], "news.api.app:main")
        self.assertEqual(scripts["news-search"], "news.cli.workflow:main")
