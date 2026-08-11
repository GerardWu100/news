"""Google Trends adapter built on the ``pytrends`` library.

``pytrends`` calls the same private endpoints that power trends.google.com.
There is no official public API, so this module is the only place that imports
the library or touches a pandas DataFrame. Everything else in the project sees
the :class:`news.trends.models.TrendsClient` interface, which means replacing a
broken library is a one-file change.

Verified against the live endpoints on 2026-08-10:

- At most five keywords per request, sharing one 0-100 scale.
- Explicit historical dates work back to 2004.
- Rate limiting is aggressive, so every call goes through a shared pacer and
  one retry with backoff.
- The library's present-moment functions (``trending_searches``,
  ``today_searches``, ``realtime_trending_searches``, ``top_charts``) all
  return HTTP 404 now, and ``get_historical_interest`` was removed by the
  library itself. None of them are wrapped here; the project has no use for
  what is popular right now.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

import pandas as pd
import requests
from pytrends.exceptions import ResponseError, TooManyRequestsError
from pytrends.request import TrendReq

from news.trends.keywords import MAX_KEYWORDS
from news.trends.models import (
    GRANULARITY_DAILY,
    GRANULARITY_HOURLY,
    GRANULARITY_MONTHLY,
    GRANULARITY_UNKNOWN,
    GRANULARITY_WEEKLY,
    InterestOverTime,
    TrendsFetchError,
    TrendsValidationError,
)
from news.trends.pacing import DEFAULT_SECONDS_BETWEEN_REQUESTS, RequestPacer
from news.trends.window import build_trends_window

DEFAULT_GEO = ""
# Interface language and timezone offset sent with every request. The offset is
# in minutes west of UTC; zero keeps the returned timestamps in UTC.
HOST_LANGUAGE = "en-US"
TIMEZONE_OFFSET_MINUTES = 0
# One retry after a rate-limit response, waiting this long before it.
RATE_LIMIT_RETRY_ATTEMPTS = 1
RATE_LIMIT_RETRY_DELAY_SECONDS = 30.0
# Spacing in days between consecutive points, used to name the granularity.
DAILY_SPACING_DAYS = 1
WEEKLY_SPACING_DAYS = 7
MONTHLY_MINIMUM_SPACING_DAYS = 28


class GoogleTrendsClient:
    """Fetch search interest for a past window through ``pytrends``.

    A fresh ``TrendReq`` session is built for every call. Sessions carry Google
    tokens that expire, and building one per call keeps this object stateless
    and safe to share between threads.

    Attributes
    ----------
    pacer : RequestPacer
        Shared gap-keeper consulted before every outgoing request.
    """

    __slots__ = ("pacer",)

    def __init__(
        self,
        *,
        seconds_between_requests: float = DEFAULT_SECONDS_BETWEEN_REQUESTS,
        pacer: RequestPacer | None = None,
    ) -> None:
        """Create a client.

        Parameters
        ----------
        seconds_between_requests : float, optional
            Minimum gap between outgoing requests. Ignored when ``pacer`` is
            given.
        pacer : RequestPacer | None, optional
            An existing pacer to share with other clients. ``None`` builds one
            from ``seconds_between_requests``.
        """
        self.pacer = RequestPacer(seconds_between_requests) if pacer is None else pacer

    def interest_over_time(
        self,
        keywords: list[str],
        *,
        start_date: str,
        end_date: str,
        geo: str = DEFAULT_GEO,
    ) -> InterestOverTime:
        """Fetch the 0-100 search-interest series for an explicit past window.

        Parameters
        ----------
        keywords : list[str]
            One to five non-empty keywords. All of them share one scale, so
            their values can be compared with each other.
        start_date : str
            Inclusive window start in ``YYYY-MM-DD`` format.
        end_date : str
            Inclusive window end in ``YYYY-MM-DD`` format.
        geo : str, optional
            Geography code; the empty default means worldwide.

        Returns
        -------
        InterestOverTime
            Aligned dates, partial flags, and one series per keyword, with the
            window and the granularity Google actually returned.

        Raises
        ------
        TrendsValidationError
            If the keywords or the dates are unusable.
        TrendsFetchError
            If Google rejects the request, rate limits it, or the network
            fails.
        """
        cleaned_keywords = _validated_keywords(keywords)
        window = build_trends_window(start_date, end_date)

        frame = self._fetch_with_retry(
            lambda: _build_payload(
                cleaned_keywords,
                window.to_timeframe(),
                geo.strip(),
            ).interest_over_time()
        )
        dates, partial_flags, values = _convert_interest_frame(frame, cleaned_keywords)

        return InterestOverTime(
            keywords=tuple(cleaned_keywords),
            start_date=window.start_date.isoformat(),
            end_date=window.end_date.isoformat(),
            geo=geo.strip(),
            granularity=_granularity_of(dates),
            dates=dates,
            is_partial=partial_flags,
            values=values,
            # A raw fetch is scaled by the peak of the whole window, so the
            # anchor is the last day of the window. Rebasing moves it earlier.
            anchor_date=window.end_date.isoformat(),
            fetched_at=_utc_now_iso(),
        )

    def _fetch_with_retry[ResultT](self, fetch: Callable[[], ResultT]) -> ResultT:
        """Pace, run one upstream call, and turn library errors into ours.

        Parameters
        ----------
        fetch : Callable[[], ResultT]
            Zero-argument callable performing the ``pytrends`` request.

        Returns
        -------
        ResultT
            Whatever the callable returns on success.
        """
        for attempt in range(RATE_LIMIT_RETRY_ATTEMPTS + 1):
            self.pacer.wait_for_turn()
            try:
                return fetch()
            except TooManyRequestsError as exc:
                if attempt == RATE_LIMIT_RETRY_ATTEMPTS:
                    raise TrendsFetchError(
                        "Google Trends rate limit reached (HTTP 429). Wait a "
                        "few minutes, and increase the configured gap between "
                        "requests if this keeps happening."
                    ) from exc
                time.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)
            except ResponseError as exc:
                raise TrendsFetchError(
                    f"Google Trends rejected the request: {exc}"
                ) from exc
            except requests.RequestException as exc:
                raise TrendsFetchError(f"Google Trends request failed: {exc}") from exc
        raise TrendsFetchError("Unreachable retry state.")


def _validated_keywords(keywords: list[str]) -> list[str]:
    """Strip, drop blanks, and enforce Google's five-keyword limit."""
    cleaned = [keyword.strip() for keyword in keywords if keyword.strip()]
    if not cleaned:
        raise TrendsValidationError("At least one non-empty keyword is required.")
    if len(cleaned) > MAX_KEYWORDS:
        raise TrendsValidationError(
            f"Google Trends accepts at most {MAX_KEYWORDS} keywords per request."
        )
    return cleaned


def _build_payload(keywords: list[str], timeframe: str, geo: str) -> TrendReq:
    """Build a fresh session and register the request payload with Google."""
    session = TrendReq(hl=HOST_LANGUAGE, tz=TIMEZONE_OFFSET_MINUTES)
    session.build_payload(keywords, timeframe=timeframe, geo=geo)
    return session


def _convert_interest_frame(
    frame: pd.DataFrame,
    keywords: list[str],
) -> tuple[tuple[str, ...], tuple[bool, ...], dict[str, tuple[float, ...]]]:
    """Convert the ``interest_over_time`` frame into plain aligned tuples.

    The incoming frame has a ``DatetimeIndex`` named ``date``, one integer
    column per keyword holding the 0-100 values, and a boolean ``isPartial``
    column. An empty frame means Google had no data for the request and
    converts to empty tuples rather than raising, because "no data" is a real
    answer for a rare term in an old window.
    """
    if frame.empty:
        return (), (), {keyword: () for keyword in keywords}

    # Decide the label format once for the whole series. Formatting each
    # timestamp on its own would drop the time from every point that lands on
    # midnight, so an hourly series would mix "2015-03-01" with
    # "2015-03-01 01:00" and stop being sortable or parseable.
    dates = _format_timestamps(frame.index)
    if "isPartial" in frame.columns:
        partial_flags = tuple(bool(flag) for flag in frame["isPartial"])
    else:
        partial_flags = tuple(False for _ in dates)
    # A keyword Google did not return at all becomes an all-zero series, so
    # every requested keyword stays present and aligned with ``dates``.
    values = {
        keyword: (
            tuple(float(value) for value in frame[keyword])
            if keyword in frame.columns
            else tuple(0.0 for _ in dates)
        )
        for keyword in keywords
    }
    return dates, partial_flags, values


def _granularity_of(dates: tuple[str, ...]) -> str:
    """Name the spacing of the returned points.

    Google chooses the spacing from the window length and does not report it,
    so it is read back from the first two timestamps. A caller that assumed
    daily values can then notice it received weekly ones.
    """
    if len(dates) < 2:
        return GRANULARITY_UNKNOWN
    if " " in dates[0]:
        return GRANULARITY_HOURLY

    first = datetime.strptime(dates[0], "%Y-%m-%d")
    second = datetime.strptime(dates[1], "%Y-%m-%d")
    spacing_days = (second - first).days
    if spacing_days <= DAILY_SPACING_DAYS:
        return GRANULARITY_DAILY
    if spacing_days <= WEEKLY_SPACING_DAYS:
        return GRANULARITY_WEEKLY
    if spacing_days >= MONTHLY_MINIMUM_SPACING_DAYS:
        return GRANULARITY_MONTHLY
    return GRANULARITY_UNKNOWN


def _format_timestamps(index: pd.DatetimeIndex) -> tuple[str, ...]:
    """Label every point, using the same format across the whole series.

    Daily, weekly, and monthly points all land on midnight and are labelled
    ``YYYY-MM-DD``. Hourly points carry a time, and as soon as one of them
    does, every label in the series includes the time, including the ones at
    midnight.
    """
    has_time_of_day = any(
        stamp.hour or stamp.minute or stamp.second for stamp in index
    )
    label_format = "%Y-%m-%d %H:%M" if has_time_of_day else "%Y-%m-%d"
    return tuple(stamp.strftime(label_format) for stamp in index)


def _utc_now_iso() -> str:
    """Return the current UTC time in ISO format with seconds precision."""
    return datetime.now(UTC).isoformat(timespec="seconds")
