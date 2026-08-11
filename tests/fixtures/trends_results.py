"""Offline fixtures for trends tests.

Live Google behavior is not deterministic, so tests use these fixed objects and
a fake client instead of calling the network, matching the policy the project
already applies to news providers.

The numbers are real. They come from two live fetches of the keyword "bitcoin"
for the United States that differ only in the end date, which is the measured
example of Google's window-dependent scaling.
"""

from __future__ import annotations

from news.trends.models import InterestOverTime

# Fetched with the window 2017-01-01 to 2017-09-15. The window's peak sits on
# 2017-05-25, months after these rows, which is why the January values are
# small: they are already divided by a peak that had not happened yet.
LONG_WINDOW_SERIES = InterestOverTime(
    keywords=("bitcoin",),
    start_date="2017-01-01",
    end_date="2017-09-15",
    geo="US",
    granularity="daily",
    dates=("2017-01-01", "2017-01-02", "2017-01-03", "2017-01-04", "2017-01-05"),
    is_partial=(False, False, False, False, False),
    values={"bitcoin": (14.0, 24.0, 21.0, 28.0, 30.0)},
    anchor_date="2017-09-15",
    fetched_at="2026-08-10T00:00:00+00:00",
)

# The same five days fetched with the window 2017-01-01 to 2017-03-31. Every
# value is about 3.33 times larger because the divisor is a nearer, smaller
# peak. Rebasing LONG_WINDOW_SERIES to 2017-01-05 should reproduce these
# proportions.
SHORT_WINDOW_SERIES = InterestOverTime(
    keywords=("bitcoin",),
    start_date="2017-01-01",
    end_date="2017-03-31",
    geo="US",
    granularity="daily",
    dates=("2017-01-01", "2017-01-02", "2017-01-03", "2017-01-04", "2017-01-05"),
    is_partial=(False, False, False, False, False),
    values={"bitcoin": (47.0, 80.0, 69.0, 95.0, 100.0)},
    anchor_date="2017-03-31",
    fetched_at="2026-08-10T00:00:00+00:00",
)

# Two keywords on one shared scale, used to check that rebasing keeps them
# comparable with each other.
TWO_KEYWORD_SERIES = InterestOverTime(
    keywords=("bitcoin", "ethereum"),
    start_date="2015-01-01",
    end_date="2015-01-04",
    geo="US",
    granularity="daily",
    dates=("2015-01-01", "2015-01-02", "2015-01-03", "2015-01-04"),
    is_partial=(False, False, False, True),
    values={
        "bitcoin": (27.0, 28.0, 31.0, 41.0),
        "ethereum": (0.0, 0.0, 0.0, 4.0),
    },
    anchor_date="2015-01-04",
    fetched_at="2026-08-10T00:00:00+00:00",
)


class FakeTrendsClient:
    """A ``TrendsClient`` that returns a fixed series and records its inputs.

    Attributes
    ----------
    series : InterestOverTime
        The object every call returns.
    calls : list[dict]
        One entry per call, holding the keywords, window, and geography, so a
        test can assert what the route asked for.
    """

    def __init__(self, series: InterestOverTime = TWO_KEYWORD_SERIES) -> None:
        self.series = series
        self.calls: list[dict[str, object]] = []

    def interest_over_time(
        self,
        keywords: list[str],
        *,
        start_date: str,
        end_date: str,
        geo: str = "",
    ) -> InterestOverTime:
        """Record the request and return the fixed series."""
        self.calls.append(
            {
                "keywords": list(keywords),
                "start_date": start_date,
                "end_date": end_date,
                "geo": geo,
            }
        )
        return self.series


class FailingTrendsClient:
    """A ``TrendsClient`` that always raises the given error."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def interest_over_time(
        self,
        keywords: list[str],
        *,
        start_date: str,
        end_date: str,
        geo: str = "",
    ) -> InterestOverTime:
        """Raise the configured error instead of fetching."""
        raise self.error
