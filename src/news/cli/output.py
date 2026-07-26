"""Output formatting and export helpers for the command line."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from news.exports.formats import format_csv, format_json, write_sqlite

from .parser import build_api_params


def format_table(articles: list[dict[str, Any]], meta: dict[str, Any]) -> str:
    """Render search results as a compact plain-text table.

    Parameters
    ----------
    articles : list[dict[str, Any]]
        Normalized article dictionaries from the API or direct backend path.
    meta : dict[str, Any]
        Search metadata returned by the package search pipeline.

    Returns
    -------
    str
        Human-readable table suitable for terminal output.
    """
    sources = ", ".join(meta.get("requested_sources") or []) or "all available"
    query = meta.get("query", "")
    start_date = meta.get("start", "")
    end_date = meta.get("end", "")
    returned_count = meta.get("returned", 0)
    duplicates_removed = meta.get("duplicates_removed", 0)
    page = meta.get("page", 1)

    # Keep the summary lines separate from row rendering so callers can still
    # see the request context when a page has no articles.
    lines = [
        f'News Search: "{query}" | {start_date} to {end_date} | Sources: {sources}',
        (
            f"{returned_count} results "
            f"({duplicates_removed} duplicates removed) | "
            f"Page {page}"
        ),
        "",
    ]
    if not articles:
        lines.append("No results found.")
        return "\n".join(lines)

    date_width = max(10, *(len(article.get("date", "")) for article in articles))
    source_width = max(8, *(len(article.get("source", "")) for article in articles))
    domain_width = max(12, *(len(article.get("domain", "")) for article in articles))
    title_width = 58

    lines.append(
        " #  "
        f"{'Date':<{date_width}}  "
        f"{'Source':<{source_width}}  "
        f"{'Title':<{title_width}}  "
        f"{'Domain':<{domain_width}}"
    )

    for index, article in enumerate(articles, start=1):
        title = truncate(article.get("title", ""), title_width)
        lines.append(
            f"{index:>2}  "
            f"{article.get('date', ''):<{date_width}}  "
            f"{article.get('source', ''):<{source_width}}  "
            f"{title:<{title_width}}  "
            f"{article.get('domain', ''):<{domain_width}}"
        )

    if meta.get("has_more"):
        next_page = page + 1
        lines.extend(
            [
                "",
                (
                    f"Page {page} | "
                    f"{returned_count} results shown | "
                    f"More pages available (use --page {next_page} "
                    "or --all-pages)"
                ),
            ]
        )

    return "\n".join(lines)


def write_export(
    args: argparse.Namespace,
    articles: list[dict[str, Any]],
    output_path: Path,
    meta: dict[str, Any],
) -> None:
    """Write search results to disk in the requested format.

    This keeps API passthrough export behavior for single-page CSV/JSON calls,
    but falls back to local serialization for direct mode or multi-page exports.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if should_download_api_export(args, meta):
        output_path.write_text(download_api_export(args), encoding="utf-8")
        return

    write_local_export(args, articles, output_path)


def write_local_export(
    args: argparse.Namespace,
    articles: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """Serialize search results locally without calling the HTTP export route."""
    if args.export == "csv":
        output_path.write_text(
            format_csv(articles, include_content=args.include_content),
            encoding="utf-8",
        )
        return

    if args.export == "json":
        output_path.write_text(format_json(articles), encoding="utf-8")
        return

    write_sqlite(articles, str(output_path), query=args.query)


def download_api_export(args: argparse.Namespace) -> str:
    """Download a single-page API export directly from the package API."""
    export_path = f"/api/export/{args.export}"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(
            f"{args.server.rstrip('/')}{export_path}",
            params=build_api_params(args),
        )
        response.raise_for_status()
        return response.text


def should_download_api_export(
    args: argparse.Namespace,
    meta: dict[str, Any],
) -> bool:
    """Return ``True`` when CLI export can stream directly from the API."""
    if args.direct:
        return False
    if args.all_pages:
        return False
    if args.export not in {"csv", "json"}:
        return False

    response_page = int(meta.get("page", args.page))
    return response_page == args.page


def resolve_output_path(args: argparse.Namespace) -> Path:
    """Resolve the destination path for an export file."""
    if args.output:
        return Path(args.output).expanduser().resolve()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_query = "-".join(args.query.lower().split())[:40] or "search"
    suffix = {"csv": ".csv", "json": ".json", "sqlite": ".db"}[args.export]
    filename = f"{safe_query}-{args.start}-{args.end}-{timestamp}{suffix}"
    return (Path.cwd() / filename).resolve()


def truncate(value: str, width: int) -> str:
    """Trim a value to fit a fixed-width table column."""
    if len(value) <= width:
        return value
    return f"{value[: width - 3].rstrip()}..."
