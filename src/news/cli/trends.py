"""Command-line client for Google Trends data.

Unlike ``news-search``, this command calls the trends package directly
instead of going through the HTTP API: Google Trends needs no server-held
credentials and no cross-provider orchestration, so a server round-trip
would add a dependency without adding capability.

Subcommands mirror the three API endpoints:

- ``interest``: 0-100 search-interest series for up to five keywords.
- ``regions``: regional 0-100 breakdown for up to five keywords.
- ``related``: top and rising related queries for one keyword.

Output formats: an aligned text table (default), ``json`` (one indented
object including the fetch timestamp), or ``csv`` on standard output for
redirection into a file.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from typing import Any

from news.trends import (
    GoogleTrendsClient,
    InterestByRegion,
    InterestOverTime,
    RelatedQueries,
    TrendsClient,
    TrendsFetchError,
    TrendsValidationError,
)
from news.trends.google import DEFAULT_GEO, DEFAULT_RESOLUTION, DEFAULT_TIMEFRAME

OUTPUT_FORMATS = ("table", "json", "csv")


def main(argv: list[str] | None = None) -> int:
    """Run the trends CLI.

    Parameters
    ----------
    argv : list[str] | None, optional
        Command arguments. ``None`` reads the process arguments.

    Returns
    -------
    int
        ``0`` on success, ``1`` on validation or upstream failure.
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        print(run_command(args, client=GoogleTrendsClient()))
        return 0
    except (TrendsValidationError, TrendsFetchError) as exc:
        print(f"news-trends failed: {exc.message}", file=sys.stderr)
        return 1


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the ``news-trends`` argument parser with its three subcommands."""
    parser = argparse.ArgumentParser(
        prog="news-trends",
        description=(
            "Fetch Google Trends relative search interest (0-100 index). "
            "Values are scaled within the requested window and keyword set; "
            "absolute search counts are never available."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    interest = subparsers.add_parser(
        "interest",
        help="Interest-over-time series for up to 5 keywords",
    )
    _add_shared_arguments(interest, multiple_keywords=True)

    regions = subparsers.add_parser(
        "regions",
        help="Regional interest breakdown for up to 5 keywords",
    )
    _add_shared_arguments(regions, multiple_keywords=True)
    regions.add_argument(
        "--resolution",
        default=DEFAULT_RESOLUTION,
        choices=("COUNTRY", "REGION", "CITY", "DMA"),
        help=(
            "Breakdown granularity: COUNTRY, REGION (state/province), CITY, "
            f"or DMA (United States metro areas) (default: {DEFAULT_RESOLUTION})"
        ),
    )

    related = subparsers.add_parser(
        "related",
        help="Top and rising related queries for one keyword",
    )
    _add_shared_arguments(related, multiple_keywords=False)

    return parser


def _add_shared_arguments(
    parser: argparse.ArgumentParser,
    *,
    multiple_keywords: bool,
) -> None:
    """Attach the keyword, window, geography, and format options."""
    if multiple_keywords:
        parser.add_argument("keywords", nargs="+", help="1 to 5 keywords")
    else:
        parser.add_argument("keyword", help="One keyword")
    parser.add_argument(
        "--timeframe",
        default=DEFAULT_TIMEFRAME,
        help=(
            "Google timeframe expression, for example 'today 3-m', 'today 5-y', "
            f"or '2025-01-01 2025-06-30' (default: '{DEFAULT_TIMEFRAME}')"
        ),
    )
    parser.add_argument(
        "--geo",
        default=DEFAULT_GEO,
        help="Geography code, for example US or US-NY (default: worldwide)",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        default="table",
        choices=OUTPUT_FORMATS,
        help="Output format (default: table)",
    )


def run_command(args: argparse.Namespace, *, client: TrendsClient) -> str:
    """Execute one parsed subcommand and return its rendered output.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command arguments.
    client : TrendsClient
        Trends client; tests inject an offline fake.

    Returns
    -------
    str
        Rendered table, JSON document, or CSV text.
    """
    if args.command == "interest":
        result = client.interest_over_time(
            args.keywords, timeframe=args.timeframe, geo=args.geo
        )
        return _render(args.output_format, result.to_dict(), _interest_rows(result))
    if args.command == "regions":
        result = client.interest_by_region(
            args.keywords,
            timeframe=args.timeframe,
            geo=args.geo,
            resolution=args.resolution,
        )
        return _render(args.output_format, result.to_dict(), _region_rows(result))
    result = client.related_queries(
        args.keyword, timeframe=args.timeframe, geo=args.geo
    )
    return _render(args.output_format, result.to_dict(), _related_rows(result))


def _interest_rows(result: InterestOverTime) -> list[list[str]]:
    """Flatten a series result to header-plus-rows for table and CSV output."""
    header = ["date", *result.keywords, "is_partial"]
    rows = [header]
    for position, date in enumerate(result.dates):
        rows.append(
            [
                date,
                *(str(result.values[keyword][position]) for keyword in result.keywords),
                str(result.is_partial[position]).lower(),
            ]
        )
    return rows


def _region_rows(result: InterestByRegion) -> list[list[str]]:
    """Flatten a regional result to header-plus-rows for table and CSV output."""
    header = ["region", *result.keywords]
    rows = [header]
    for region in result.regions:
        rows.append(
            [
                region.region,
                *(str(region.values[keyword]) for keyword in result.keywords),
            ]
        )
    return rows


def _related_rows(result: RelatedQueries) -> list[list[str]]:
    """Flatten related queries to header-plus-rows for table and CSV output.

    ``value`` is the 0-100 volume index for ``top`` rows and percent growth
    for ``rising`` rows.
    """
    rows = [["kind", "query", "value"]]
    rows.extend(["top", row.query, str(row.value)] for row in result.top)
    rows.extend(["rising", row.query, str(row.value)] for row in result.rising)
    return rows


def _render(
    output_format: str,
    payload: dict[str, Any],
    rows: list[list[str]],
) -> str:
    """Render one result as a table, JSON document, or CSV text."""
    if output_format == "json":
        return json.dumps(payload, indent=2, ensure_ascii=False)
    if output_format == "csv":
        buffer = io.StringIO()
        csv.writer(buffer, lineterminator="\n").writerows(rows)
        return buffer.getvalue().rstrip("\n")
    return _format_table(rows)


def _format_table(rows: list[list[str]]) -> str:
    """Align header-plus-rows into fixed-width columns."""
    if len(rows) == 1:
        return "No data returned."
    widths = [
        max(len(row[column]) for row in rows) for column in range(len(rows[0]))
    ]
    lines = [
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        for row in rows
    ]
    separator = "  ".join("-" * width for width in widths)
    return "\n".join([lines[0], separator, *lines[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
