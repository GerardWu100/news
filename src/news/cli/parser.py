"""Argument parsing helpers for the news search command line."""

from __future__ import annotations

import argparse

DEFAULT_EXPORT_MAX_PAGES = 50
DEFAULT_SERVER_URL = "http://localhost:8000"
DEFAULT_PROVIDER_SORT = "default"


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for search and export workflows."""
    parser = argparse.ArgumentParser(
        description="Search historical news across multiple providers.",
    )
    parser.add_argument("query", help="Search keywords")
    parser.add_argument("-s", "--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("-e", "--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--sources", default="", help="Comma-separated source names")
    parser.add_argument(
        "--english", action="store_true", help="Shortcut for --language en"
    )
    parser.add_argument("-l", "--language", default="", help="Language filter")
    parser.add_argument(
        "--no-dedupe", action="store_true", help="Disable deduplication"
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
        help="Provider ranking mode",
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
        "--all-pages", action="store_true", help="Fetch and combine all pages"
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_EXPORT_MAX_PAGES,
        help="Safety limit for --all-pages",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print raw JSON instead of a table"
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
        default=DEFAULT_SERVER_URL,
        help="Base URL for the running API server",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Bypass the server and call the backend pipeline directly",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress messages"
    )
    return parser


def build_api_params(
    args: argparse.Namespace,
    page: int | None = None,
) -> dict[str, str]:
    """Map parsed CLI arguments to the backend API parameter contract."""
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
