"""Tests for the ``news-trends`` command, without touching the network."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from news.cli import trends as trends_cli
from news.trends.models import TrendsFetchError, TrendsValidationError
from tests.fixtures.trends_results import LONG_WINDOW_SERIES, TWO_KEYWORD_SERIES


class TrendsCliRenderingTests(unittest.TestCase):
    """Output formats a person or a tool reads."""

    def test_table_shows_the_scale_details(self) -> None:
        """The header states the window and anchor the values depend on."""
        rendered = trends_cli.render(TWO_KEYWORD_SERIES, "table")

        self.assertIn("bitcoin, ethereum", rendered)
        self.assertIn("2015-01-01 to 2015-01-04", rendered)
        self.assertIn("daily points", rendered)
        self.assertIn("on or before 2015-01-04", rendered)

    def test_table_marks_a_still_accumulating_period(self) -> None:
        """A partial point is labelled so it is not read as final."""
        rendered = trends_cli.render(TWO_KEYWORD_SERIES, "table")

        self.assertIn("still accumulating", rendered)

    def test_table_reports_an_empty_result_plainly(self) -> None:
        """No data is stated, not shown as an empty table."""
        empty_series = type(TWO_KEYWORD_SERIES)(
            keywords=("rare-term",),
            start_date="2005-01-01",
            end_date="2005-06-30",
            geo="",
            granularity="unknown",
            dates=(),
            is_partial=(),
            values={"rare-term": ()},
            anchor_date="2005-06-30",
            fetched_at="2026-08-10T00:00:00+00:00",
        )

        self.assertIn("No data returned", trends_cli.render(empty_series, "table"))

    def test_json_output_round_trips(self) -> None:
        """Tools receive every field, including the window and anchor."""
        payload = json.loads(trends_cli.render(TWO_KEYWORD_SERIES, "json"))

        self.assertEqual(payload["keywords"], ["bitcoin", "ethereum"])
        self.assertEqual(payload["anchor_date"], "2015-01-04")
        self.assertEqual(payload["values"]["ethereum"], [0.0, 0.0, 0.0, 4.0])

    def test_csv_output_has_one_row_per_point(self) -> None:
        """Spreadsheet output keeps the keywords as columns."""
        rendered = trends_cli.render(TWO_KEYWORD_SERIES, "csv")
        lines = rendered.splitlines()

        self.assertEqual(lines[0], "date,bitcoin,ethereum,is_partial")
        self.assertEqual(lines[1], "2015-01-01,27,0,false")
        self.assertEqual(len(lines), 5)

    def test_rebased_values_keep_two_decimals(self) -> None:
        """Fractional values from rescaling are shown, not silently rounded."""
        from news.trends.rebase import rebase_as_of

        rebased = rebase_as_of(LONG_WINDOW_SERIES, "2017-01-05")
        rendered = trends_cli.render(rebased, "csv")

        self.assertIn("46.67", rendered)


class TrendsCliCommandTests(unittest.TestCase):
    """Argument handling and exit status."""

    def test_successful_run_prints_and_exits_zero(self) -> None:
        """A working fetch prints the table and reports success."""
        with (
            patch.object(trends_cli, "fetch_series", return_value=TWO_KEYWORD_SERIES),
            patch("builtins.print") as fake_print,
        ):
            status = trends_cli.main(
                ["bitcoin", "-s", "2015-01-01", "-e", "2015-01-04"]
            )

        self.assertEqual(status, 0)
        self.assertIn("bitcoin", fake_print.call_args[0][0])

    def test_validation_error_exits_one(self) -> None:
        """A bad window is reported on standard error, not as a crash."""
        with (
            patch.object(
                trends_cli,
                "fetch_series",
                side_effect=TrendsValidationError("start_date must be earlier"),
            ),
            patch("builtins.print"),
        ):
            status = trends_cli.main(
                ["bitcoin", "-s", "2015-06-30", "-e", "2015-01-01"]
            )

        self.assertEqual(status, 1)

    def test_upstream_error_exits_one(self) -> None:
        """A Google failure is reported the same way."""
        with (
            patch.object(
                trends_cli,
                "fetch_series",
                side_effect=TrendsFetchError("rate limit reached"),
            ),
            patch("builtins.print"),
        ):
            status = trends_cli.main(
                ["bitcoin", "-s", "2015-01-01", "-e", "2015-01-04"]
            )

        self.assertEqual(status, 1)

    def test_as_of_is_applied_to_the_fetched_series(self) -> None:
        """The command rebases locally rather than refetching."""
        parser = trends_cli.build_arg_parser()
        args = parser.parse_args(
            [
                "bitcoin",
                "-s",
                "2017-01-01",
                "-e",
                "2017-09-15",
                "--as-of",
                "2017-01-03",
            ]
        )

        class StubClient:
            """Return the fixture regardless of the request."""

            def __init__(self, **_settings: object) -> None:
                """Accept the pacing settings the command passes in."""

            def interest_over_time(self, *args: object, **kwargs: object) -> object:
                return LONG_WINDOW_SERIES

        with (
            patch.object(trends_cli, "GoogleTrendsClient", StubClient),
            patch.object(trends_cli, "load_settings") as fake_settings,
        ):
            fake_settings.return_value.trends.seconds_between_requests = 0.0
            fake_settings.return_value.trends.default_geo = ""
            series = trends_cli.fetch_series(args)

        self.assertEqual(series.anchor_date, "2017-01-03")
        self.assertEqual(len(series.dates), 3)


if __name__ == "__main__":
    unittest.main()
