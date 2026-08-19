"""Tests for the Google Trends adapter, without touching the network.

Every test builds a fake ``pytrends`` session, so the DataFrame conversion,
validation, pacing, and error mapping are exercised offline.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd
import requests
from pytrends.exceptions import ResponseError, TooManyRequestsError

from news.trends import google
from news.trends.google import GoogleTrendsClient
from news.trends.models import TrendsFetchError, TrendsValidationError


def build_interest_frame(
    dates: list[str],
    values: dict[str, list[int]],
    partial_flags: list[bool] | None = None,
) -> pd.DataFrame:
    """Build a frame shaped like the one ``interest_over_time`` returns."""
    frame = pd.DataFrame(values, index=pd.to_datetime(dates))
    frame.index.name = "date"
    frame["isPartial"] = partial_flags or [False] * len(dates)
    return frame


class FakeSession:
    """Stand-in for ``TrendReq`` that returns a prepared frame."""

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.payload: dict[str, object] = {}

    def build_payload(
        self,
        keywords: list[str],
        timeframe: str = "",
        geo: str = "",
    ) -> None:
        """Record what was requested instead of calling Google."""
        self.payload = {"keywords": keywords, "timeframe": timeframe, "geo": geo}

    def interest_over_time(self) -> pd.DataFrame:
        """Return the prepared frame."""
        return self.frame


def client_without_pacing() -> GoogleTrendsClient:
    """Build a client whose pacer never sleeps, so tests run instantly."""
    return GoogleTrendsClient(seconds_between_requests=0.0)


class InterestOverTimeConversionTests(unittest.TestCase):
    """Turning a pandas frame into the project's plain result object."""

    def test_frame_becomes_aligned_tuples(self) -> None:
        """Dates, flags, and one series per keyword all line up."""
        frame = build_interest_frame(
            ["2015-01-01", "2015-01-02"],
            {"bitcoin": [27, 28], "ethereum": [0, 4]},
            partial_flags=[False, True],
        )
        session = FakeSession(frame)

        with patch.object(google, "TrendReq", return_value=session):
            series = client_without_pacing().interest_over_time(
                ["bitcoin", "ethereum"],
                start_date="2015-01-01",
                end_date="2015-01-02",
                geo="US",
            )

        self.assertEqual(series.dates, ("2015-01-01", "2015-01-02"))
        self.assertEqual(series.values["bitcoin"], (27.0, 28.0))
        self.assertEqual(series.values["ethereum"], (0.0, 4.0))
        self.assertEqual(series.is_partial, (False, True))
        self.assertEqual(series.keywords, ("bitcoin", "ethereum"))
        self.assertEqual(series.geo, "US")

    def test_window_is_sent_as_explicit_dates(self) -> None:
        """The timeframe never uses a today-anchored shorthand."""
        session = FakeSession(
            build_interest_frame(["2015-01-01"], {"bitcoin": [27]}),
        )

        with patch.object(google, "TrendReq", return_value=session):
            client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-01-01",
                end_date="2015-06-30",
            )

        self.assertEqual(session.payload["timeframe"], "2015-01-01 2015-06-30")

    def test_raw_fetch_is_anchored_to_the_window_end(self) -> None:
        """A fetched series records that its scale came from the whole window."""
        session = FakeSession(
            build_interest_frame(["2015-01-01"], {"bitcoin": [27]}),
        )

        with patch.object(google, "TrendReq", return_value=session):
            series = client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-01-01",
                end_date="2015-06-30",
            )

        self.assertEqual(series.anchor_date, "2015-06-30")

    def test_daily_spacing_is_reported(self) -> None:
        """Granularity is read back from the timestamps Google returned."""
        session = FakeSession(
            build_interest_frame(
                ["2015-01-01", "2015-01-02"],
                {"bitcoin": [27, 28]},
            )
        )

        with patch.object(google, "TrendReq", return_value=session):
            series = client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-01-01",
                end_date="2015-01-02",
            )

        self.assertEqual(series.granularity, "daily")

    def test_weekly_spacing_is_reported(self) -> None:
        """A long window silently returns weekly points, and that is visible."""
        session = FakeSession(
            build_interest_frame(
                ["2015-01-04", "2015-01-11", "2015-01-18"],
                {"bitcoin": [27, 28, 31]},
            )
        )

        with patch.object(google, "TrendReq", return_value=session):
            series = client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-01-01",
                end_date="2015-12-31",
            )

        self.assertEqual(series.granularity, "weekly")

    def test_hourly_timestamps_keep_their_time(self) -> None:
        """A one-week window returns hourly points labelled with the hour."""
        session = FakeSession(
            build_interest_frame(
                ["2015-03-01 00:00", "2015-03-01 01:00"],
                {"bitcoin": [38, 39]},
            )
        )

        with patch.object(google, "TrendReq", return_value=session):
            series = client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-03-01",
                end_date="2015-03-07",
            )

        self.assertEqual(series.granularity, "hourly")
        self.assertEqual(series.dates[1], "2015-03-01 01:00")

    def test_empty_frame_is_not_an_error(self) -> None:
        """No data for a rare term in an old window is a real answer."""
        session = FakeSession(pd.DataFrame())

        with patch.object(google, "TrendReq", return_value=session):
            series = client_without_pacing().interest_over_time(
                ["a-very-rare-term"],
                start_date="2005-01-01",
                end_date="2005-06-30",
            )

        self.assertEqual(series.dates, ())
        self.assertEqual(series.values["a-very-rare-term"], ())


class InterestOverTimeValidationTests(unittest.TestCase):
    """Input checks that run before any network call."""

    def test_no_keywords_is_rejected(self) -> None:
        """An empty keyword list cannot produce a series."""
        with self.assertRaises(TrendsValidationError):
            client_without_pacing().interest_over_time(
                ["  "],
                start_date="2015-01-01",
                end_date="2015-06-30",
            )

    def test_more_than_five_keywords_is_rejected(self) -> None:
        """Google's shared scale holds at most five terms."""
        with self.assertRaises(TrendsValidationError):
            client_without_pacing().interest_over_time(
                ["a", "b", "c", "d", "e", "f"],
                start_date="2015-01-01",
                end_date="2015-06-30",
            )

    def test_reversed_window_is_rejected(self) -> None:
        """The end date cannot precede the start date."""
        with self.assertRaises(TrendsValidationError):
            client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-06-30",
                end_date="2015-01-01",
            )

    def test_future_window_is_rejected_before_the_network(self) -> None:
        """Historical retrieval must not accept dates after today."""
        with self.assertRaisesRegex(TrendsValidationError, "after today"):
            client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2099-01-01",
                end_date="2099-01-02",
            )

    def test_today_anchored_timeframe_is_rejected(self) -> None:
        """Google's shorthands are unreproducible and never accepted."""
        with self.assertRaises(TrendsValidationError):
            client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="today 3-m",
                end_date="2015-06-30",
            )

    def test_date_before_the_archive_is_rejected(self) -> None:
        """Google's history starts in 2004."""
        with self.assertRaises(TrendsValidationError):
            client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="1999-01-01",
                end_date="2015-06-30",
            )


class UpstreamFailureTests(unittest.TestCase):
    """Library and network errors become one project error type."""

    def test_rate_limit_retries_once_then_reports(self) -> None:
        """A persistent HTTP 429 produces a plain-language failure."""
        call_count = 0

        def always_rate_limited(*args: object, **kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            raise TooManyRequestsError("429", response=None)

        with (
            patch.object(google, "TrendReq", side_effect=always_rate_limited),
            patch.object(google.time, "sleep"),
            self.assertRaises(TrendsFetchError) as caught,
        ):
            client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-01-01",
                end_date="2015-06-30",
            )

        self.assertEqual(call_count, google.RATE_LIMIT_RETRY_ATTEMPTS + 1)
        self.assertIn("rate limit", caught.exception.message.lower())

    def test_rate_limit_succeeds_on_the_retry(self) -> None:
        """One transient HTTP 429 does not fail the request."""
        session = FakeSession(
            build_interest_frame(["2015-01-01"], {"bitcoin": [27]}),
        )
        attempts = [TooManyRequestsError("429", response=None), session]

        def rate_limited_once(*args: object, **kwargs: object) -> FakeSession:
            outcome = attempts.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with (
            patch.object(google, "TrendReq", side_effect=rate_limited_once),
            patch.object(google.time, "sleep"),
        ):
            series = client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-01-01",
                end_date="2015-06-30",
            )

        self.assertEqual(series.values["bitcoin"], (27.0,))

    def test_rejected_request_becomes_a_fetch_error(self) -> None:
        """A Google refusal is reported as an upstream failure."""
        with (
            patch.object(
                google,
                "TrendReq",
                side_effect=ResponseError("bad request", response=None),
            ),
            self.assertRaises(TrendsFetchError),
        ):
            client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-01-01",
                end_date="2015-06-30",
            )

    def test_network_failure_becomes_a_fetch_error(self) -> None:
        """A dropped connection is reported the same way."""
        with (
            patch.object(
                google,
                "TrendReq",
                side_effect=requests.ConnectionError("no route"),
            ),
            self.assertRaises(TrendsFetchError),
        ):
            client_without_pacing().interest_over_time(
                ["bitcoin"],
                start_date="2015-01-01",
                end_date="2015-06-30",
            )


class PacingTests(unittest.TestCase):
    """Requests are spaced so Google's rate limit is not tripped."""

    def test_every_request_waits_for_its_turn(self) -> None:
        """The pacer is consulted before the call reaches the library."""
        session = FakeSession(
            build_interest_frame(["2015-01-01"], {"bitcoin": [27]}),
        )
        client = client_without_pacing()

        class CountingPacer:
            """Record how many times a caller asked for its turn."""

            def __init__(self) -> None:
                self.waits = 0

            def wait_for_turn(self) -> None:
                self.waits += 1

        counting_pacer = CountingPacer()
        client.pacer = counting_pacer

        with patch.object(google, "TrendReq", return_value=session):
            client.interest_over_time(
                ["bitcoin"],
                start_date="2015-01-01",
                end_date="2015-06-30",
            )

        self.assertEqual(counting_pacer.waits, 1)


if __name__ == "__main__":
    unittest.main()
