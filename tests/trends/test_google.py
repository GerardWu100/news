"""Offline tests for pytrends frame conversion, validation, and retries."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import pandas as pd
from pytrends.exceptions import ResponseError, TooManyRequestsError

from news.trends.google import (
    _call_with_rate_limit_retry,
    _convert_interest_frame,
    _convert_region_frame,
    _convert_related_payload,
    _validated_keywords,
)
from news.trends.models import TrendsFetchError, TrendsValidationError


class KeywordValidationTests(unittest.TestCase):
    """Keyword rules should fail fast before any network call."""

    def test_strips_and_drops_empty_keywords(self) -> None:
        """Whitespace-only entries disappear and real ones are trimmed."""
        self.assertEqual(_validated_keywords([" bitcoin ", "", "  "]), ["bitcoin"])

    def test_rejects_empty_keyword_list(self) -> None:
        """An all-empty request should raise a validation error."""
        with self.assertRaises(TrendsValidationError):
            _validated_keywords(["", "   "])

    def test_rejects_more_than_five_keywords(self) -> None:
        """Google's five-keyword request limit should be enforced locally."""
        with self.assertRaises(TrendsValidationError):
            _validated_keywords(["a", "b", "c", "d", "e", "f"])


class InterestFrameConversionTests(unittest.TestCase):
    """The interest-over-time DataFrame should flatten to aligned tuples."""

    def test_converts_daily_frame(self) -> None:
        """Dates, partial flags, and per-keyword series stay aligned."""
        frame = pd.DataFrame(
            {"bitcoin": [40, 60], "isPartial": [False, True]},
            index=pd.to_datetime(["2026-08-01", "2026-08-02"]),
        )

        dates, partial_flags, values = _convert_interest_frame(frame, ["bitcoin"])

        self.assertEqual(dates, ("2026-08-01", "2026-08-02"))
        self.assertEqual(partial_flags, (False, True))
        self.assertEqual(values, {"bitcoin": (40, 60)})

    def test_hourly_timestamps_keep_time_of_day(self) -> None:
        """Intraday points must not collapse to bare dates."""
        frame = pd.DataFrame(
            {"bitcoin": [10], "isPartial": [False]},
            index=pd.to_datetime(["2026-08-01 14:00:00"]),
        )

        dates, _, _ = _convert_interest_frame(frame, ["bitcoin"])

        self.assertEqual(dates, ("2026-08-01 14:00",))

    def test_empty_frame_converts_to_empty_series(self) -> None:
        """No upstream data should mean empty tuples, not an error."""
        dates, partial_flags, values = _convert_interest_frame(
            pd.DataFrame(), ["bitcoin"]
        )

        self.assertEqual(dates, ())
        self.assertEqual(partial_flags, ())
        self.assertEqual(values, {"bitcoin": ()})


class RegionFrameConversionTests(unittest.TestCase):
    """The regional DataFrame should flatten to one row per region."""

    def test_converts_region_frame(self) -> None:
        """Region names and per-keyword values survive conversion."""
        frame = pd.DataFrame(
            {"bitcoin": [100, 55]},
            index=pd.Index(["New York", "Texas"], name="geoName"),
        )

        rows = _convert_region_frame(frame, ["bitcoin"])

        self.assertEqual(rows[0].region, "New York")
        self.assertEqual(rows[0].values, {"bitcoin": 100})
        self.assertEqual(rows[1].region, "Texas")

    def test_empty_frame_converts_to_no_rows(self) -> None:
        """No regional data should mean an empty tuple."""
        self.assertEqual(_convert_region_frame(pd.DataFrame(), ["bitcoin"]), ())


class RelatedPayloadConversionTests(unittest.TestCase):
    """The related-queries payload should flatten to top and rising rows."""

    def test_converts_top_and_rising_frames(self) -> None:
        """Both lists convert with their query and value columns."""
        payload = {
            "bitcoin": {
                "top": pd.DataFrame({"query": ["bitcoin price"], "value": [100]}),
                "rising": pd.DataFrame({"query": ["bitcoin crash"], "value": [250]}),
            }
        }

        top, rising = _convert_related_payload(payload, "bitcoin")

        self.assertEqual(top[0].query, "bitcoin price")
        self.assertEqual(top[0].value, 100)
        self.assertEqual(rising[0].query, "bitcoin crash")

    def test_missing_frames_convert_to_empty_lists(self) -> None:
        """Google returning no data must not raise."""
        top, rising = _convert_related_payload({"bitcoin": {"top": None}}, "bitcoin")

        self.assertEqual(top, ())
        self.assertEqual(rising, ())


class RateLimitRetryTests(unittest.TestCase):
    """Upstream failures should map onto the package's own error types."""

    def test_retries_once_then_succeeds(self) -> None:
        """A single rate-limit response should be retried after a delay."""
        fetch = Mock(side_effect=[TooManyRequestsError("429", Mock()), "data"])

        with patch("news.trends.google.time.sleep") as fake_sleep:
            result = _call_with_rate_limit_retry(fetch)

        self.assertEqual(result, "data")
        self.assertEqual(fetch.call_count, 2)
        fake_sleep.assert_called_once()

    def test_persistent_rate_limit_raises_fetch_error(self) -> None:
        """Exhausted retries should surface as a TrendsFetchError."""
        fetch = Mock(side_effect=TooManyRequestsError("429", Mock()))

        with patch("news.trends.google.time.sleep"):
            with self.assertRaises(TrendsFetchError):
                _call_with_rate_limit_retry(fetch)

    def test_response_error_raises_fetch_error_without_retry(self) -> None:
        """Non-rate-limit upstream rejections should fail immediately."""
        fetch = Mock(side_effect=ResponseError("400", Mock()))

        with self.assertRaises(TrendsFetchError):
            _call_with_rate_limit_retry(fetch)
        self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
