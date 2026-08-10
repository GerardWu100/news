"""Google Trends adapter built on the ``pytrends`` library.

``pytrends`` scrapes the same private endpoints that power the
trends.google.com website. There is no official public API, so this module
isolates every ``pytrends`` call and DataFrame conversion behind the
``TrendsClient`` interface; if Google breaks the library, only this module
changes.

Known limits of the upstream endpoints as of 2026-08:

- At most five keywords per request; values are relative across the batch.
- Aggressive rate limiting (HTTP 429) on repeated calls; this module retries
  with exponential backoff, so callers should still space out bulk fetches.
- ``related_topics``, ``trending_searches``, and ``multirange_interest`` are
  broken upstream and are intentionally not wrapped here.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime

import pandas as pd
import requests
from pytrends.exceptions import ResponseError, TooManyRequestsError
from pytrends.request import TrendReq

from news.trends.models import (
    InterestByRegion,
    InterestOverTime,
    RegionInterest,
    RelatedQueries,
    RelatedQuery,
    TrendsFetchError,
    TrendsValidationError,
)

MAX_KEYWORDS_PER_REQUEST = 5
DEFAULT_TIMEFRAME = "today 12-m"
DEFAULT_GEO = ""
DEFAULT_RESOLUTION = "COUNTRY"
VALID_RESOLUTIONS = ("COUNTRY", "REGION", "CITY", "DMA")
# Interface language and timezone offset sent with every request. The offset
# is minutes west of UTC; 0 keeps returned dates in UTC.
HOST_LANGUAGE = "en-US"
TIMEZONE_OFFSET_MINUTES = 0
# One retry after a rate-limit response, with exponential backoff seconds.
RATE_LIMIT_RETRY_ATTEMPTS = 1
RATE_LIMIT_BASE_DELAY_SECONDS = 5.0


class GoogleTrendsClient:
    """Production ``TrendsClient`` implementation backed by ``pytrends``.

    A fresh ``TrendReq`` session is built per call: sessions hold Google
    tokens that expire, and per-call construction keeps the client stateless
    and safe to share across threads.
    """

    def interest_over_time(
        self,
        keywords: list[str],
        *,
        timeframe: str = DEFAULT_TIMEFRAME,
        geo: str = DEFAULT_GEO,
    ) -> InterestOverTime:
        """Fetch the 0-100 search-interest series for up to five keywords.

        Parameters
        ----------
        keywords : list[str]
            One to five non-empty keywords; values are scaled jointly.
        timeframe : str, optional
            Google timeframe expression, for example ``today 3-m``,
            ``today 5-y``, or ``2025-01-01 2025-06-30``.
        geo : str, optional
            Geography code; empty string means worldwide.

        Returns
        -------
        InterestOverTime
            Aligned dates, partial flags, and one series per keyword.
        """
        cleaned = _validated_keywords(keywords)
        frame = _call_with_rate_limit_retry(
            lambda: _build_payload(cleaned, timeframe, geo).interest_over_time()
        )
        dates, partial_flags, values = _convert_interest_frame(frame, cleaned)
        return InterestOverTime(
            keywords=tuple(cleaned),
            timeframe=timeframe,
            geo=geo,
            dates=dates,
            is_partial=partial_flags,
            values=values,
            fetched_at=_utc_now_iso(),
        )

    def interest_by_region(
        self,
        keywords: list[str],
        *,
        timeframe: str = DEFAULT_TIMEFRAME,
        geo: str = DEFAULT_GEO,
        resolution: str = DEFAULT_RESOLUTION,
    ) -> InterestByRegion:
        """Fetch the regional interest breakdown for up to five keywords.

        Parameters
        ----------
        keywords : list[str]
            One to five non-empty keywords.
        timeframe : str, optional
            Google timeframe expression.
        geo : str, optional
            Geography code scoping the breakdown; empty means worldwide.
        resolution : str, optional
            ``COUNTRY``, ``REGION``, ``CITY``, or ``DMA``.

        Returns
        -------
        InterestByRegion
            One row per region Google reports; low-volume regions are omitted.
        """
        cleaned = _validated_keywords(keywords)
        normalized_resolution = resolution.upper()
        if normalized_resolution not in VALID_RESOLUTIONS:
            raise TrendsValidationError(
                f"resolution must be one of {', '.join(VALID_RESOLUTIONS)}."
            )
        frame = _call_with_rate_limit_retry(
            lambda: _build_payload(cleaned, timeframe, geo).interest_by_region(
                resolution=normalized_resolution,
                inc_low_vol=False,
            )
        )
        return InterestByRegion(
            keywords=tuple(cleaned),
            timeframe=timeframe,
            geo=geo,
            resolution=normalized_resolution,
            regions=_convert_region_frame(frame, cleaned),
            fetched_at=_utc_now_iso(),
        )

    def related_queries(
        self,
        keyword: str,
        *,
        timeframe: str = DEFAULT_TIMEFRAME,
        geo: str = DEFAULT_GEO,
    ) -> RelatedQueries:
        """Fetch top and rising related queries for one keyword.

        Parameters
        ----------
        keyword : str
            Single non-empty keyword.
        timeframe : str, optional
            Google timeframe expression.
        geo : str, optional
            Geography code; empty means worldwide.

        Returns
        -------
        RelatedQueries
            ``top`` holds 0-100 relative volume; ``rising`` holds percent
            growth where breakout growth appears as a very large number.
        """
        cleaned = _validated_keywords([keyword])
        payload = _call_with_rate_limit_retry(
            lambda: _build_payload(cleaned, timeframe, geo).related_queries()
        )
        top, rising = _convert_related_payload(payload, cleaned[0])
        return RelatedQueries(
            keyword=cleaned[0],
            timeframe=timeframe,
            geo=geo,
            top=top,
            rising=rising,
            fetched_at=_utc_now_iso(),
        )


def _validated_keywords(keywords: list[str]) -> list[str]:
    """Strip, drop empties, and enforce the five-keyword upstream limit."""
    cleaned = [keyword.strip() for keyword in keywords if keyword.strip()]
    if not cleaned:
        raise TrendsValidationError("At least one non-empty keyword is required.")
    if len(cleaned) > MAX_KEYWORDS_PER_REQUEST:
        raise TrendsValidationError(
            f"Google Trends accepts at most {MAX_KEYWORDS_PER_REQUEST} keywords "
            "per request."
        )
    return cleaned


def _build_payload(keywords: list[str], timeframe: str, geo: str) -> TrendReq:
    """Build a fresh session and register the request payload with Google."""
    session = TrendReq(hl=HOST_LANGUAGE, tz=TIMEZONE_OFFSET_MINUTES)
    session.build_payload(keywords, timeframe=timeframe, geo=geo)
    return session


def _call_with_rate_limit_retry[ResultT](fetch: Callable[[], ResultT]) -> ResultT:
    """Run one upstream call, retrying rate limits and wrapping failures.

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
        try:
            return fetch()
        except TooManyRequestsError as exc:
            if attempt == RATE_LIMIT_RETRY_ATTEMPTS:
                raise TrendsFetchError(
                    "Google Trends rate limit hit (HTTP 429). Wait a minute "
                    "before retrying and space out bulk fetches."
                ) from exc
            # Exponential backoff: base, 2x base, ...
            time.sleep(RATE_LIMIT_BASE_DELAY_SECONDS * (2**attempt))
        except ResponseError as exc:
            raise TrendsFetchError(f"Google Trends rejected the request: {exc}") from exc
        except requests.RequestException as exc:
            raise TrendsFetchError(f"Google Trends request failed: {exc}") from exc
    raise TrendsFetchError("Unreachable retry state.")


def _convert_interest_frame(
    frame: pd.DataFrame,
    keywords: list[str],
) -> tuple[tuple[str, ...], tuple[bool, ...], dict[str, tuple[int, ...]]]:
    """Convert the ``interest_over_time`` DataFrame to plain aligned tuples.

    Input frame: DatetimeIndex named ``date``; one 0-100 integer column per
    keyword plus a boolean ``isPartial`` column. An empty frame (no data for
    the query) converts to empty tuples rather than an error.
    """
    if frame.empty:
        return (), (), {keyword: () for keyword in keywords}
    dates = tuple(_format_timestamp(stamp) for stamp in frame.index)
    if "isPartial" in frame.columns:
        partial_flags = tuple(bool(flag) for flag in frame["isPartial"])
    else:
        partial_flags = tuple(False for _ in dates)
    values = {
        keyword: tuple(int(value) for value in frame[keyword]) for keyword in keywords
    }
    return dates, partial_flags, values


def _convert_region_frame(
    frame: pd.DataFrame,
    keywords: list[str],
) -> tuple[RegionInterest, ...]:
    """Convert the ``interest_by_region`` DataFrame to plain rows.

    Input frame: index of region names (``geoName``); one 0-100 integer
    column per keyword.
    """
    if frame.empty:
        return ()
    return tuple(
        RegionInterest(
            region=str(region),
            values={keyword: int(row[keyword]) for keyword in keywords},
        )
        for region, row in frame.iterrows()
    )


def _convert_related_payload(
    payload: dict[str, dict[str, pd.DataFrame | None]],
    keyword: str,
) -> tuple[tuple[RelatedQuery, ...], tuple[RelatedQuery, ...]]:
    """Convert the ``related_queries`` payload to plain top and rising rows.

    Input payload: ``{keyword: {"top": frame | None, "rising": frame | None}}``
    where each frame has ``query`` (string) and ``value`` (integer) columns.
    Missing frames mean Google had no data and convert to empty tuples.
    """
    per_keyword = payload.get(keyword, {})
    return (
        _convert_related_frame(per_keyword.get("top")),
        _convert_related_frame(per_keyword.get("rising")),
    )


def _convert_related_frame(
    frame: pd.DataFrame | None,
) -> tuple[RelatedQuery, ...]:
    """Convert one related-queries DataFrame, treating ``None`` as empty."""
    if frame is None or frame.empty:
        return ()
    return tuple(
        RelatedQuery(query=str(row["query"]), value=int(row["value"]))
        for _, row in frame.iterrows()
    )


def _format_timestamp(stamp: pd.Timestamp) -> str:
    """Render midnight timestamps as dates and intraday ones with time."""
    if stamp.hour == 0 and stamp.minute == 0 and stamp.second == 0:
        return stamp.strftime("%Y-%m-%d")
    return stamp.strftime("%Y-%m-%d %H:%M")


def _utc_now_iso() -> str:
    """Return the current UTC time in ISO format with seconds precision."""
    return datetime.now(UTC).isoformat(timespec="seconds")
