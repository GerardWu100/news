"""Tests for turning a news search query into Google Trends keywords."""

from __future__ import annotations

import unittest

from news.trends.keywords import keywords_from_query
from news.trends.models import TrendsValidationError


class KeywordExtractionTests(unittest.TestCase):
    """The bridge from a boolean article query to plain search terms."""

    def test_plain_words_become_separate_keywords(self) -> None:
        """A simple query keeps each word, in order."""
        self.assertEqual(
            keywords_from_query("inflation recession"),
            ("inflation", "recession"),
        )

    def test_quoted_phrase_stays_one_keyword(self) -> None:
        """Quotes group words so a phrase is searched as a phrase."""
        self.assertEqual(
            keywords_from_query('"central bank" inflation'),
            ("central bank", "inflation"),
        )

    def test_boolean_operators_are_dropped(self) -> None:
        """AND and OR join terms and are not search terms themselves."""
        self.assertEqual(
            keywords_from_query("inflation AND rates OR yields"),
            ("inflation", "rates", "yields"),
        )

    def test_parentheses_are_stripped(self) -> None:
        """Grouping characters are structure, not part of any term."""
        self.assertEqual(
            keywords_from_query("(inflation OR rates)"),
            ("inflation", "rates"),
        )

    def test_excluded_terms_are_removed(self) -> None:
        """Trends cannot express exclusion, so excluded terms are dropped."""
        self.assertEqual(
            keywords_from_query("bitcoin -crypto NOT mining ethereum"),
            ("bitcoin", "ethereum"),
        )

    def test_commas_separate_keywords(self) -> None:
        """The comma-separated syntax shown by the CLI must not keep commas."""
        self.assertEqual(
            keywords_from_query("inflation, recession"),
            ("inflation", "recession"),
        )

    def test_excluded_quoted_phrase_is_removed_as_one_token(self) -> None:
        """A minus sign before quotes excludes the complete phrase."""
        self.assertEqual(
            keywords_from_query('bitcoin -"crypto mining"'),
            ("bitcoin",),
        )

    def test_repeats_are_removed_ignoring_capitalization(self) -> None:
        """The first spelling wins and later repeats are skipped."""
        self.assertEqual(
            keywords_from_query("Inflation inflation INFLATION rates"),
            ("Inflation", "rates"),
        )

    def test_worked_example_from_the_module_docstring(self) -> None:
        """The documented example produces the documented result."""
        self.assertEqual(
            keywords_from_query('"central bank" AND (inflation OR Inflation) -crypto'),
            ("central bank", "inflation"),
        )

    def test_extra_terms_are_dropped_at_the_limit(self) -> None:
        """A long article query still yields a usable five-keyword request."""
        self.assertEqual(
            keywords_from_query("one two three four five six seven"),
            ("one", "two", "three", "four", "five"),
        )

    def test_custom_limit_is_respected(self) -> None:
        """Callers may ask for fewer keywords than Google's maximum."""
        self.assertEqual(
            keywords_from_query("one two three", max_keywords=2),
            ("one", "two"),
        )

    def test_blank_query_is_rejected(self) -> None:
        """An empty query cannot produce a series."""
        with self.assertRaises(TrendsValidationError):
            keywords_from_query("   ")

    def test_query_of_only_operators_is_rejected(self) -> None:
        """Operators and exclusions alone leave nothing to search."""
        with self.assertRaises(TrendsValidationError):
            keywords_from_query("AND OR -crypto")


if __name__ == "__main__":
    unittest.main()
