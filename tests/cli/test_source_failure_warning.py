"""A search where most sources failed must not read like a complete search.

The header names every requested source and the summary counts the articles
returned. Without a warning, six sources where four failed looks exactly like
six sources where four had no matching articles. For research on a fixed
historical window that difference decides whether the result can be used.
"""

from __future__ import annotations

import unittest

from news.cli.output import format_source_failures, format_table

ARTICLE = {
    "title": "Prices rise",
    "url": "https://example.com/a",
    "date": "2025-01-02",
    "source": "guardian",
    "domain": "theguardian.com",
}


def _meta(source_reports: list[dict[str, object]]) -> dict[str, object]:
    """Build the search details a CLI response carries."""
    return {
        "query": "inflation",
        "start": "2025-01-01",
        "end": "2025-03-01",
        "requested_sources": [report["name"] for report in source_reports],
        "returned": 1,
        "duplicates_removed": 0,
        "page": 1,
        "has_more": False,
        "source_reports": source_reports,
    }


class SourceFailureWarningTests(unittest.TestCase):
    """Verify failures are stated, counted, and explained."""

    def test_failed_sources_are_named_with_their_reason(self) -> None:
        """The reader needs the source name and what to do about it."""
        lines = format_source_failures(
            _meta(
                [
                    {"name": "gdelt", "error": "Source rate limited this query."},
                    {"name": "newsapi", "error": "Plan does not reach that far back."},
                    {"name": "guardian", "error": ""},
                ]
            )
        )

        joined = "\n".join(lines)
        self.assertIn("2 of 3", joined)
        self.assertIn("gdelt", joined)
        self.assertIn("rate limited", joined)
        self.assertIn("newsapi", joined)
        self.assertNotIn("guardian", joined)

    def test_no_warning_when_every_source_answered(self) -> None:
        """A clean search must stay quiet."""
        lines = format_source_failures(
            _meta([{"name": "guardian", "error": ""}]),
        )

        self.assertEqual(lines, [])

    def test_table_shows_the_warning_above_the_rows(self) -> None:
        """The warning belongs next to the counts it qualifies."""
        table = format_table(
            [ARTICLE],
            _meta(
                [
                    {"name": "gdelt", "error": "Source rate limited this query."},
                    {"name": "guardian", "error": ""},
                ]
            ),
        )

        warning_position = table.index("Warning:")
        row_position = table.index("Prices rise")
        self.assertLess(warning_position, row_position)

    def test_table_warns_even_when_no_articles_were_returned(self) -> None:
        """"No results found" is misleading when every source refused."""
        table = format_table(
            [],
            _meta([{"name": "gdelt", "error": "Source rate limited this query."}]),
        )

        self.assertIn("Warning:", table)
        self.assertIn("No results found.", table)

    def test_missing_source_reports_do_not_break_the_table(self) -> None:
        """An older response without reports should still render."""
        meta = _meta([])
        meta.pop("source_reports")

        self.assertEqual(format_source_failures(meta), [])
        self.assertIn("Prices rise", format_table([ARTICLE], meta))


if __name__ == "__main__":
    unittest.main()
