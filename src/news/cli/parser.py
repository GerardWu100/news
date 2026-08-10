"""Argument parsing helpers for the ``news-search`` command."""

from __future__ import annotations

import argparse
import os

DEFAULT_EXPORT_MAX_PAGES = 50
DEFAULT_SERVER_URL = "http://localhost:8000"
SERVER_URL_ENVIRONMENT_VARIABLE = "NEWS_SERVER_URL"
DEFAULT_PROVIDER_SORT = "default"
OUTPUT_FORMATS = ("table", "json", "jsonl")

CLI_EXAMPLES = """examples:
  Readable search for a person:
    news-search "central bank" -s 2025-01-01 -e 2025-01-31

  Structured output for a large language model (LLM):
    news-search "central bank" -s 2025-01-01 -e 2025-01-31 \\
      --all-pages --format json

  One JSON article per line for a stream:
    news-search "earnings" -s 2025-02-01 -e 2025-02-07 \\
      --sources guardian,nyt --format jsonl

The start and end dates are inclusive publication-date boundaries. Results can
still be incomplete because each source has different archive and pagination
limits.
"""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for search and export commands."""
    default_server_url = (
        os.getenv(SERVER_URL_ENVIRONMENT_VARIABLE, "").strip() or DEFAULT_SERVER_URL
    )
    parser = argparse.ArgumentParser(
        description=(
            "Retrieve news published within an inclusive historical date window."
        ),
        epilog=CLI_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", help="Keywords or source-supported query expression")
    parser.add_argument(
        "-s",
        "--start",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive publication start date",
    )
    parser.add_argument(
        "-e",
        "--end",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive publication end date (the research cutoff)",
    )
    parser.add_argument("--sources", default="", help="Comma-separated source names")
    parser.add_argument(
        "--english", action="store_true", help="Shortcut for --language en"
    )
    parser.add_argument("-l", "--language", default="", help="Language filter")
    parser.add_argument(
        "--no-dedupe", action="store_true", help="Keep duplicate articles"
    )
    parser.add_argument("--exact-phrase", default="", help="Require exact phrase")
    parser.add_argument("--exclude", default="", help="Comma-separated exclude terms")
    parser.add_argument("--domain", default="", help="Comma-separated include domains")
    parser.add_argument(
        "--exclude-domains",
        default="",
        help="Comma-separated exclude domains",
    )
    parser.add_argument(
        "--scope",
        default="all",
        choices=["all", "title"],
        help="Search scope for local filtering",
    )
    parser.add_argument(
        "--match",
        default="provider",
        choices=["provider", "all_terms", "any_term"],
        help="Keyword match mode",
    )
    parser.add_argument(
        "--sort",
        default="date_desc",
        choices=["date_desc", "date_asc"],
        help="Sort order",
    )
    parser.add_argument(
        "--provider-sort",
        default=DEFAULT_PROVIDER_SORT,
        help="Source ranking mode",
    )
    parser.add_argument("--section", default="", help="Comma-separated section filters")
    parser.add_argument("--news-desk", default="", help="Comma-separated NYT desks")
    parser.add_argument(
        "--guardian-tag", default="", help="Comma-separated Guardian tags"
    )
    parser.add_argument(
        "--newsapi-search-in", default="all", help="NewsAPI field scope"
    )
    parser.add_argument("-p", "--page", type=int, default=1, help="Page number")
    parser.add_argument(
        "--all-pages", action="store_true", help="Fetch and combine every page"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_EXPORT_MAX_PAGES,
        help="Maximum pages for --all-pages",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=OUTPUT_FORMATS,
        default="table",
        help=(
            "Output format: table for people, json for tools/LLMs, "
            "or jsonl for one article per line (default: table)"
        ),
    )
    parser.add_argument(
        "--json",
        dest="output_format",
        action="store_const",
        const="json",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--export",
        choices=["csv", "json", "sqlite"],
        help="Write results to a file",
    )
    parser.add_argument("-o", "--output", default="", help="Output path for export")
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="Include content in CSV exports",
    )
    parser.add_argument(
        "--server",
        default=default_server_url,
        help=(
            "Base URL of the running API server "
            f"(default: ${SERVER_URL_ENVIRONMENT_VARIABLE} or {DEFAULT_SERVER_URL})"
        ),
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Skip the server and call the search code directly",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress messages"
    )
    return parser


def build_api_params(
    args: argparse.Namespace,
    page: int | None = None,
) -> dict[str, str]:
    """Map parsed CLI arguments to the API parameter format."""
    language = "en" if args.english else args.language.strip()
    params: dict[str, str] = {
        "q": args.query,
        "start": args.start,
        "end": args.end,
        "dedupe": "false" if args.no_dedupe else "true",
        "page": str(args.page if page is None else page),
        "language": language,
        "exact_phrase": args.exact_phrase,
        "exclude_terms": args.exclude,
        "domain": args.domain,
        "exclude_domains": args.exclude_domains,
        "search_scope": args.scope,
        "match_mode": args.match,
        "provider_sort": args.provider_sort,
        "section": args.section,
        "news_desk": args.news_desk,
        "guardian_tag": args.guardian_tag,
        "newsapi_search_in": args.newsapi_search_in,
        "sort": args.sort,
    }
    if args.sources:
        params["sources"] = args.sources
    return params
