"""Coordinate the top-level ``news-search`` command."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from typing import Any

import httpx
from dotenv import load_dotenv

from news.search.deduplication import deduplicate_articles
from news.search.errors import SearchValidationError
from news.search.filters import sort_articles
from news.sources.base import Article
from news.web.paths import env_path

from .fetch import fetch_page
from .output import (
    format_source_failures,
    format_table,
    resolve_output_path,
    write_export,
)
from .parser import build_arg_parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    # Load the operator’s default remote endpoint before building the parser;
    # explicit shell environment variables still take precedence.
    load_dotenv(env_path())
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        run_cli(args)
        return 0
    except SearchValidationError as exc:
        print(f"CLI failed: {exc.message}", file=sys.stderr)
        return 1
    except (httpx.HTTPError, OSError, RuntimeError, sqlite3.Error, ValueError) as exc:
        print(f"CLI failed: {exc}", file=sys.stderr)
        return 1


def run_cli(args: argparse.Namespace) -> None:
    """Execute the parsed CLI request.

    The table is handled first because it is the one output a person reads, and
    it carries its own failure warning inline next to the counts. Every other
    output is meant for a program, so its warning goes to the error stream.
    """
    payload = collect_results(args)

    if not args.export and args.output_format == "table":
        print(format_table(payload["results"], payload["meta"]))
        return

    warn_about_failed_sources(args, payload["meta"])

    if args.export:
        output_path = resolve_output_path(args)
        write_export(args, payload["results"], output_path, payload["meta"])
        if not args.quiet:
            print(f"Exported {len(payload['results'])} articles to {output_path}")
        return

    if args.output_format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    # The parser accepts only table, json, and jsonl, so this is jsonl.
    for article in payload["results"]:
        print(json.dumps(article, ensure_ascii=False, separators=(",", ":")))


def warn_about_failed_sources(
    args: argparse.Namespace,
    meta: dict[str, Any],
) -> None:
    """Report failed sources on the error stream for machine-readable output.

    JSON, JSON Lines, and file exports must stay parseable, so the warning goes
    to standard error instead of into the data. ``--quiet`` suppresses it
    because a script that asked for silence already has ``source_reports`` in
    the payload.
    """
    if args.quiet:
        return

    for line in format_source_failures(meta):
        print(line, file=sys.stderr)


def collect_results(args: argparse.Namespace) -> dict[str, Any]:
    """Fetch results from the API, direct search code, or several pages."""
    if args.all_pages:
        return collect_all_pages(args)
    return fetch_page(args, page=args.page)


def collect_all_pages(args: argparse.Namespace) -> dict[str, Any]:
    """Read several pages and combine them into one CLI response.

    The loop stops when the backend says no more pages are available or when
    the ``--max-pages`` safety limit is hit. An empty locally filtered page does
    not stop collection while a provider still reports another page.
    """
    if args.max_pages < 1:
        raise ValueError("--max-pages must be at least 1.")

    combined_results: list[dict[str, Any]] = []
    total_duplicates_removed = 0
    combined_source_reports: dict[str, dict[str, Any]] = {}

    for offset in range(args.max_pages):
        page = args.page + offset
        payload = fetch_page(args, page=page)

        articles = payload["results"]
        page_meta = payload["meta"]
        combined_results.extend(articles)
        total_duplicates_removed += int(page_meta["duplicates_removed"])
        _merge_source_reports(
            combined_source_reports,
            page_meta.get("source_reports") or [],
            page=page,
        )

        if not args.quiet:
            print(
                f"Fetching page {page}... ({len(combined_results)} articles so far)",
                file=sys.stderr,
            )

        # A page can become empty only after local filters run while a provider
        # still has another page. Trust explicit pagination state so filtered
        # gaps do not truncate the historical result set.
        if not page_meta["has_more"]:
            break
    else:
        raise RuntimeError(f"Reached the --max-pages safety limit ({args.max_pages}).")

    # A positive max-pages limit guarantees that page_meta was set.
    if not args.no_dedupe:
        combined_articles = [_article_from_payload(row) for row in combined_results]
        deduplicated_articles = deduplicate_articles(combined_articles)
        total_duplicates_removed += len(combined_articles) - len(deduplicated_articles)
        combined_results = [
            article.to_dict()
            for article in sort_articles(deduplicated_articles, args.sort)
        ]

    combined_meta = dict(page_meta)
    combined_meta["page"] = args.page
    combined_meta["returned"] = len(combined_results)
    combined_meta["total"] = len(combined_results)
    combined_meta["duplicates_removed"] = total_duplicates_removed
    combined_meta["has_more"] = False
    combined_meta["has_previous"] = args.page > 1
    combined_meta["source_reports"] = list(combined_source_reports.values())
    return {"results": combined_results, "meta": combined_meta}


def _article_from_payload(payload: dict[str, Any]) -> Article:
    """Rebuild one normalized article for cross-page deduplication.

    Parameters
    ----------
    payload : dict[str, Any]
        JSON-ready article returned by one source page.

    Returns
    -------
    Article
        Shared article model containing every normalized field.
    """
    return Article(
        title=str(payload.get("title", "")),
        url=str(payload.get("url", "")),
        date=str(payload.get("date", "")),
        source=str(payload.get("source", "")),
        domain=str(payload.get("domain", "")),
        language=str(payload.get("language", "")),
        summary=str(payload.get("summary", "")),
        content=str(payload.get("content", "")),
        section=str(payload.get("section", "")),
        author=str(payload.get("author", "")),
        matched_sources=tuple(payload.get("matched_sources") or ()),
        duplicate_count=int(payload.get("duplicate_count", 1)),
    )


def _merge_source_reports(
    combined_reports: dict[str, dict[str, Any]],
    page_reports: list[dict[str, Any]],
    *,
    page: int,
) -> None:
    """Accumulate provider coverage without losing an earlier page failure.

    Parameters
    ----------
    combined_reports : dict[str, dict[str, Any]]
        Mutable provider-name mapping accumulated across pages.
    page_reports : list[dict[str, Any]]
        Provider reports returned for the current page.
    page : int
        One-based page number used to identify a failure's origin.
    """
    for report in page_reports:
        source_name = str(report.get("name", ""))
        if source_name not in combined_reports:
            combined_reports[source_name] = {
                "name": source_name,
                "display_name": report.get("display_name", source_name),
                "available": bool(report.get("available", False)),
                "requested": bool(report.get("requested", True)),
                "returned": 0,
                "has_more": False,
                "error": "",
            }

        combined = combined_reports[source_name]
        combined["available"] = bool(combined["available"] or report.get("available"))
        combined["returned"] = int(combined["returned"]) + int(
            report.get("returned", 0)
        )
        error = str(report.get("error", "")).strip()
        if error:
            page_error = f"Page {page}: {error}"
            existing_error = str(combined["error"])
            if page_error not in existing_error:
                combined["error"] = "; ".join(
                    part for part in (existing_error, page_error) if part
                )


if __name__ == "__main__":
    raise SystemExit(main())
