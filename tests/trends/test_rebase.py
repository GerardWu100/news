"""Tests for rescaling a series to one decision date."""

from __future__ import annotations

import unittest

from news.trends.models import InterestOverTime, TrendsValidationError
from news.trends.rebase import rebase_as_of
from tests.fixtures.trends_results import (
    LONG_WINDOW_SERIES,
    SHORT_WINDOW_SERIES,
    TWO_KEYWORD_SERIES,
)


class RebaseAsOfTests(unittest.TestCase):
    """Removing the future peak that Google's own scaling encodes."""

    def test_later_points_are_dropped(self) -> None:
        """Nothing after the decision date survives."""
        rebased = rebase_as_of(LONG_WINDOW_SERIES, "2017-01-03")

        self.assertEqual(rebased.dates, ("2017-01-01", "2017-01-02", "2017-01-03"))
        self.assertEqual(len(rebased.values["bitcoin"]), 3)

    def test_highest_known_value_becomes_one_hundred(self) -> None:
        """The scale is anchored to the peak that had already happened."""
        rebased = rebase_as_of(LONG_WINDOW_SERIES, "2017-01-05")

        self.assertEqual(max(rebased.values["bitcoin"]), 100.0)

    def test_rebasing_reproduces_the_shorter_window_fetch(self) -> None:
        """The cheap local rescaling matches what a narrower fetch returned.

        Both fixtures are real fetches of the same five days that differ only
        in the end date. Rebasing the long-window fetch to the last of those
        days should land within rounding distance of the short-window fetch,
        which is the whole argument for doing this locally instead of paying
        for one request per decision date.
        """
        rebased = rebase_as_of(LONG_WINDOW_SERIES, "2017-01-05")

        for rebased_value, directly_fetched in zip(
            rebased.values["bitcoin"],
            SHORT_WINDOW_SERIES.values["bitcoin"],
            strict=True,
        ):
            # Google returns whole numbers, so each fetch carries up to half a
            # unit of rounding; two units of tolerance covers both series.
            self.assertAlmostEqual(rebased_value, directly_fetched, delta=2.0)

    def test_ratios_between_days_are_unchanged(self) -> None:
        """Rescaling multiplies by a constant, so relative shape survives."""
        original = LONG_WINDOW_SERIES.values["bitcoin"]
        rebased = rebase_as_of(LONG_WINDOW_SERIES, "2017-01-05").values["bitcoin"]

        self.assertAlmostEqual(
            original[1] / original[0],
            rebased[1] / rebased[0],
            places=2,
        )

    def test_keywords_share_one_divisor(self) -> None:
        """Both keywords keep their relative sizes after rescaling.

        Google puts every keyword in a request on one shared scale. Rescaling
        each keyword against its own maximum would make a rare term look as
        popular as a common one, so a single divisor is used for all of them.
        """
        rebased = rebase_as_of(TWO_KEYWORD_SERIES, "2015-01-04")

        self.assertEqual(max(rebased.values["bitcoin"]), 100.0)
        self.assertLess(max(rebased.values["ethereum"]), 100.0)
        self.assertAlmostEqual(
            rebased.values["ethereum"][3] / rebased.values["bitcoin"][3],
            4.0 / 41.0,
            places=4,
        )

    def test_anchor_and_end_dates_move_to_the_decision_date(self) -> None:
        """The stored window records what the new scale is anchored to."""
        rebased = rebase_as_of(LONG_WINDOW_SERIES, "2017-01-03")

        self.assertEqual(rebased.anchor_date, "2017-01-03")
        self.assertEqual(rebased.end_date, "2017-01-03")
        self.assertEqual(rebased.start_date, "2017-01-01")

    def test_original_series_is_not_modified(self) -> None:
        """Rebasing returns a new object and leaves the fetch untouched."""
        rebase_as_of(LONG_WINDOW_SERIES, "2017-01-02")

        self.assertEqual(LONG_WINDOW_SERIES.anchor_date, "2017-09-15")
        self.assertEqual(len(LONG_WINDOW_SERIES.dates), 5)

    def test_partial_flags_stay_aligned(self) -> None:
        """Truncation keeps the flags lined up with the dates."""
        rebased = rebase_as_of(TWO_KEYWORD_SERIES, "2015-01-03")

        self.assertEqual(len(rebased.is_partial), len(rebased.dates))
        self.assertEqual(rebased.is_partial, (False, False, False))

    def test_date_outside_the_window_is_rejected(self) -> None:
        """A decision date the series cannot cover is a caller error."""
        with self.assertRaises(TrendsValidationError):
            rebase_as_of(LONG_WINDOW_SERIES, "2018-01-01")

    def test_malformed_date_is_rejected(self) -> None:
        """Only exact calendar dates are accepted, never Google shorthands."""
        with self.assertRaises(TrendsValidationError):
            rebase_as_of(LONG_WINDOW_SERIES, "today 3-m")

    def test_weekly_period_cannot_be_relabelled_as_known_midweek(self) -> None:
        """A weekly aggregate may contain days after a midweek decision date."""
        weekly_series = InterestOverTime(
            keywords=("inflation",),
            start_date="2017-01-01",
            end_date="2017-01-31",
            geo="US",
            granularity="weekly",
            dates=("2017-01-01", "2017-01-08", "2017-01-15"),
            is_partial=(False, False, False),
            values={"inflation": (20.0, 30.0, 40.0)},
            anchor_date="2017-01-31",
            fetched_at="2026-08-19T00:00:00+00:00",
        )

        with self.assertRaisesRegex(TrendsValidationError, "hourly or daily"):
            rebase_as_of(weekly_series, "2017-01-03")


if __name__ == "__main__":
    unittest.main()
