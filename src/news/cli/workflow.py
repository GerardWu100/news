"""Top-level command-line workflow orchestration."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from typing import Any

import httpx
from dotenv import load_dotenv

from news.search.errors import SearchValidationError
from news.web.paths import env_path

from .fetch import fetch_page
from .output import format_table, resolve_output_path, write_export
from .parser import build_arg_parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    # Load the operator's default remote endpoint before parser construction;
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
    """Execute the parsed CLI request."""
    payload = collect_results(args)
    if args.export:
        output_path = resolve_output_path(args)
        write_export(args, payload["results"], output_path, payload["meta"])
        if not args.quiet:
            print(f"Exported {len(payload['results'])} articles to {output_path}")
        return

    if args.output_format == "json":
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    if args.output_format == "jsonl":
        for article in payload["results"]:
            print(json.dumps(article, ensure_ascii=False, separators=(",", ":")))
        return

    print(format_table(payload["results"], payload["meta"]))


def collect_results(args: argparse.Namespace) -> dict[str, Any]:
    """Fetch search results from the API, direct backend, or paged aggregate."""
    if args.all_pages:
        return collect_all_pages(args)
    return fetch_page(args, page=args.page)


def collect_all_pages(args: argparse.Namespace) -> dict[str, Any]:
    """Iterate through pages and combine them into one CLI payload.

    The loop stops when the backend says no more pages are available, when an
    empty page is returned, or when the ``--max-pages`` safety limit is hit.
    """
    if args.max_pages < 1:
        raise ValueError("--max-pages must be at least 1.")

    combined_results: list[dict[str, Any]] = []
    total_duplicates_removed = 0

    for offset in range(args.max_pages):
        page = args.page + offset
        payload = fetch_page(args, page=page)

        articles = payload["results"]
        page_meta = payload["meta"]
        combined_results.extend(articles)
        total_duplicates_removed += int(page_meta["duplicates_removed"])

        if not args.quiet:
            print(
                f"Fetching page {page}... ({len(combined_results)} articles so far)",
                file=sys.stderr,
            )

        if not page_meta["has_more"] or not articles:
            break
    else:
        raise RuntimeError(f"Reached the --max-pages safety limit ({args.max_pages}).")

    # A positive max-pages limit guarantees at least one fetched page.
    combined_meta = dict(page_meta)
    combined_meta["page"] = args.page
    combined_meta["returned"] = len(combined_results)
    combined_meta["total"] = len(combined_results)
    combined_meta["duplicates_removed"] = total_duplicates_removed
    combined_meta["has_more"] = False
    combined_meta["has_previous"] = args.page > 1
    return {"results": combined_results, "meta": combined_meta}


if __name__ == "__main__":
    raise SystemExit(main())
