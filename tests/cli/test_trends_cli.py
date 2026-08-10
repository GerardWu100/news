"""Parser and rendering tests for the news-trends command line."""

from __future__ import annotations

import json
import unittest

from news.cli.trends import build_arg_parser, run_command
from tests.fixtures.trends_results import FakeTrendsClient


class TrendsCliTests(unittest.TestCase):
    """Verify argument parsing and each output format offline."""

    def setUp(self) -> None:
        """Share one parser and offline client across cases."""
        self.parser = build_arg_parser()
        self.client = FakeTrendsClient()

    def test_interest_table_renders_aligned_columns(self) -> None:
        """The default table should carry a header, rule, and data rows."""
        args = self.parser.parse_args(["interest", "bitcoin", "ethereum"])

        output = run_command(args, client=self.client)

        lines = output.splitlines()
        self.assertIn("date", lines[0])
        self.assertIn("bitcoin", lines[0])
        self.assertTrue(set(lines[1]) <= {"-", " "})
        self.assertIn("2026-08-01", lines[2])

    def test_interest_json_includes_fetch_timestamp(self) -> None:
        """JSON output should round-trip the full result payload."""
        args = self.parser.parse_args(["interest", "bitcoin", "--format", "json"])

        payload = json.loads(run_command(args, client=self.client))

        self.assertEqual(payload["values"]["bitcoin"], [40, 60])
        self.assertIn("fetched_at", payload)

    def test_regions_csv_renders_one_row_per_region(self) -> None:
        """CSV output should carry the header plus each region row."""
        args = self.parser.parse_args(
            ["regions", "bitcoin", "--resolution", "REGION", "--format", "csv"]
        )

        output = run_command(args, client=self.client)

        self.assertEqual(
            output.splitlines(),
            ["region,bitcoin", "New York,100", "Texas,55"],
        )

    def test_related_table_labels_top_and_rising(self) -> None:
        """Related output should distinguish the two list kinds."""
        args = self.parser.parse_args(["related", "bitcoin"])

        output = run_command(args, client=self.client)

        self.assertIn("top", output)
        self.assertIn("rising", output)
        self.assertIn("bitcoin crash", output)

    def test_parser_rejects_missing_subcommand(self) -> None:
        """Running without a subcommand should exit with usage."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])


if __name__ == "__main__":
    unittest.main()
