"""The ``news-trends`` command: search attention for a past window.

The command takes the same query and dates as ``news-search``, so a study can
retrieve articles and the matching public-attention series with two commands
that differ only in the program name.

Unlike ``news-search`` this never talks to the server. Google Trends needs no
stored credentials and no coordination between sources, so the command calls
the package directly and works without a running server.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys

from news.trends.google import GoogleTrendsClient
from news.trends.keywords import MAX_KEYWORDS, keywords_from_query
from news.trends.models import (
    InterestOverTime,
    TrendsFetchError,
    TrendsValidationError,
)
from news.trends.rebase import rebase_as_of
from news.web.config import SettingsError, load_settings

OUTPUT_FORMATS = ("table", "json", "csv")
# Width of the date column in table output; the longest label is an hourly
# timestamp such as "2015-03-01 13:00".
DATE_COLUMN_WIDTH = 16
# Width of each keyword column, wide enough for a rebased value like "100.00".
VALUE_COLUMN_WIDTH = 10

CLI_EXAMPLES = """examples:
  Attention during the same window as a news search:
    news-trends "central bank" -s 2015-01-01 -e 2015-06-30 --geo US

  Only what was knowable on one decision date:
    news-trends "bitcoin" -s 2017-01-01 -e 2017-09-15 --as-of 2017-01-31

  Machine-readable output:
    news-trends "inflation, recession" -s 2020-01-01 -e 2020-06-30 --format json

Values are Google's relative 0-100 index, never absolute search counts. 100 is
the highest point on or before the anchor date and everything else is scaled
against it, so two series fetched over different windows are not comparable.
A 0 can mean the term was below Google's reporting threshold.
"""


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the trends command."""
    parser = argparse.ArgumentParser(
        prog="news-trends",
        description=(
            "Retrieve Google Trends search attention for an explicit "
            "historical date window."
        ),
        epilog=CLI_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query",
        help=(
            "The same keyword query used for article search. Boolean "
            "operators and excluded terms are dropped, quoted phrases stay "
            f"whole, and at most {MAX_KEYWORDS} keywords are used."
        ),
    )
    parser.add_argument(
        "-s",
        "--start",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive window start date",
    )
    parser.add_argument(
        "-e",
        "--end",
        required=True,
        metavar="YYYY-MM-DD",
        help="Inclusive window end date",
    )
    parser.add_argument(
        "--geo",
        default="",
        help=(
            "Geography code such as US or US-NY. Omit to use the configured "
            "default, which is worldwide unless changed."
        ),
    )
    parser.add_argument(
        "--as-of",
        dest="as_of",
        default="",
        metavar="YYYY-MM-DD",
        help=(
            "Decision date inside the window. Drops later points and rescales "
            "to the highest value up to that date, so the series no longer "
            "reflects a peak that had not happened yet."
        ),
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=OUTPUT_FORMATS,
        default="table",
        help=(
            "Output format: table for people, json for tools, "
            "or csv for spreadsheets (default: table)"
        ),
    )
    parser.add_argument(
        "--config",
        default=None,
        help="TOML settings path. Overrides NEWS_CONFIG and ./config.toml.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the trends command.

    Parameters
    ----------
    argv : list[str] | None, optional
        Command arguments. ``None`` reads the process arguments.

    Returns
    -------
    int
        Process exit status: 0 on success, 1 on any handled failure.
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        series = fetch_series(args)
    except TrendsValidationError as exc:
        print(f"news-trends failed: {exc.message}", file=sys.stderr)
        return 1
    except TrendsFetchError as exc:
        print(f"news-trends failed: {exc.message}", file=sys.stderr)
        return 1
    except SettingsError as exc:
        print(f"news-trends failed to read settings: {exc}", file=sys.stderr)
        return 1

    print(render(series, args.output_format))
    return 0


def fetch_series(args: argparse.Namespace) -> InterestOverTime:
    """Turn parsed arguments into one fetched, optionally rebased series."""
    settings = load_settings(args.config)
    client = GoogleTrendsClient(
        seconds_between_requests=settings.trends.seconds_between_requests
    )
    series = client.interest_over_time(
        list(keywords_from_query(args.query)),
        start_date=args.start,
        end_date=args.end,
        geo=args.geo.strip() or settings.trends.default_geo,
    )
    if args.as_of.strip():
        series = rebase_as_of(series, args.as_of.strip())
    return series


def render(series: InterestOverTime, output_format: str) -> str:
    """Render a series in the requested output format."""
    if output_format == "json":
        return json.dumps(series.to_dict(), indent=2, ensure_ascii=False)
    if output_format == "csv":
        return format_csv(series)
    return format_table(series)


def format_table(series: InterestOverTime) -> str:
    """Render a readable table with a header describing the scale.

    The header repeats the window and the anchor date because the values mean
    nothing without them: the same day can read 100 or 30 depending on how far
    past it the request reached.
    """
    lines = [
        f"Keywords:    {', '.join(series.keywords)}",
        f"Window:      {series.start_date} to {series.end_date}"
        f" ({series.granularity} points)",
        f"Geography:   {series.geo or 'worldwide'}",
        f"Scaled to:   highest value on or before {series.anchor_date}",
        f"Fetched at:  {series.fetched_at}",
        "",
    ]

    if not series.dates:
        lines.append("No data returned for this window.")
        return "\n".join(lines)

    header = "date".ljust(DATE_COLUMN_WIDTH) + "".join(
        keyword[: VALUE_COLUMN_WIDTH - 1].rjust(VALUE_COLUMN_WIDTH)
        for keyword in series.keywords
    )
    lines.append(header)
    lines.append("-" * len(header))

    for row_index, label in enumerate(series.dates):
        row = label.ljust(DATE_COLUMN_WIDTH)
        for keyword in series.keywords:
            value = series.values[keyword][row_index]
            row += _format_value(value).rjust(VALUE_COLUMN_WIDTH)
        if series.is_partial[row_index]:
            row += "  (still accumulating)"
        lines.append(row)

    return "\n".join(lines)


def format_csv(series: InterestOverTime) -> str:
    """Render the series as comma-separated values, one row per point."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["date", *series.keywords, "is_partial"])
    for row_index, label in enumerate(series.dates):
        writer.writerow(
            [
                label,
                *(
                    _format_value(series.values[keyword][row_index])
                    for keyword in series.keywords
                ),
                str(series.is_partial[row_index]).lower(),
            ]
        )
    return buffer.getvalue().rstrip("\r\n")


def _format_value(value: float) -> str:
    """Print whole numbers without a decimal part, rebased ones with two."""
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
