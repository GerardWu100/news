"""Data models, errors, and the client interface for Google Trends data.

Google Trends returns a relative search-interest index, not articles, so these
models stay separate from the ``Article`` search schema. Every value is on
Google's 0-100 scale: 100 marks the highest interest anywhere in the requested
window and all other values are scaled against that single peak. Absolute
search counts are never available from this source.

Two fields exist because of how that scale behaves and should never be dropped
when a result is stored:

``start_date``/``end_date``
    The requested window. The 0-100 values are meaningless without it, because
    the divisor is the peak inside that window. Two series fetched over
    different windows are not comparable even for the same keyword and day.

``anchor_date``
    The last day that contributed to the divisor. A raw fetch anchors to
    ``end_date``, so values on early days already reflect a peak that may sit
    later in the window. :func:`news.trends.rebase.rebase_as_of` moves the
    anchor back to a chosen decision date, which is what removes that
    look-ahead effect. See ``docs/html/google_trends_capabilities.html``.

``fetched_at`` records the fetch time because Google computes the index from a
sample of searches: two fetches of the same window can differ slightly, and a
fetch of a past window today is not what the same request would have returned
back then.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# Granularity labels derived from the spacing of the timestamps Google returns.
# Google picks the spacing from the window length; callers never choose it.
GRANULARITY_HOURLY = "hourly"
GRANULARITY_DAILY = "daily"
GRANULARITY_WEEKLY = "weekly"
GRANULARITY_MONTHLY = "monthly"
GRANULARITY_UNKNOWN = "unknown"


class TrendsValidationError(ValueError):
    """Raised when request inputs are invalid, before any network call."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TrendsFetchError(RuntimeError):
    """Raised when Google Trends rejects, fails, or rate-limits a request."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class InterestOverTime:
    """Search-interest series for up to five keywords over one past window.

    Attributes
    ----------
    keywords : tuple[str, ...]
        Requested keywords. All of them share one scale, so their values are
        directly comparable with each other; a value twice as large means
        roughly twice the search volume on that date.
    start_date : str
        Inclusive window start in ``YYYY-MM-DD`` format, as requested.
    end_date : str
        Inclusive window end in ``YYYY-MM-DD`` format. After rebasing this is
        the decision date, because later points are dropped.
    geo : str
        Geography code: ``""`` worldwide, ``US`` country, ``US-NY`` state.
    granularity : str
        Spacing of the returned points: ``hourly``, ``daily``, ``weekly``,
        ``monthly``, or ``unknown`` for a single-point or empty result. Google
        decides this from the window length, so a caller that assumed daily
        should check it.
    dates : tuple[str, ...]
        One label per point, ``YYYY-MM-DD`` or ``YYYY-MM-DD HH:MM`` for hourly
        data. Ordered oldest first.
    is_partial : tuple[bool, ...]
        Aligned with ``dates``. ``True`` marks a period Google is still
        accumulating, whose value will change on a later fetch. A window that
        ends in the past normally has none.
    values : dict[str, tuple[float, ...]]
        Keyword to its series, aligned with ``dates``. Google returns whole
        numbers from 0 to 100; rebasing produces fractions, which is why the
        type is float. A 0 can mean "below Google's reporting threshold"
        rather than "nobody searched it".
    anchor_date : str
        The last date whose value could contribute to the divisor. Equal to
        ``end_date`` for a raw fetch; equal to the decision date after
        rebasing.
    fetched_at : str
        Fetch time in UTC, ISO format, seconds precision.
    """

    keywords: tuple[str, ...]
    start_date: str
    end_date: str
    geo: str
    granularity: str
    dates: tuple[str, ...]
    is_partial: tuple[bool, ...]
    values: dict[str, tuple[float, ...]]
    anchor_date: str
    fetched_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready mapping of every field."""
        return {
            "keywords": list(self.keywords),
            "start_date": self.start_date,
            "end_date": self.end_date,
            "geo": self.geo,
            "granularity": self.granularity,
            "dates": list(self.dates),
            "is_partial": list(self.is_partial),
            "values": {
                keyword: list(series) for keyword, series in self.values.items()
            },
            "anchor_date": self.anchor_date,
            "fetched_at": self.fetched_at,
        }


class TrendsClient(Protocol):
    """The one operation the project needs from a Google Trends source.

    Keeping the interface to a single method means the library behind it can
    be replaced by editing one module. Tests supply an offline implementation
    of this protocol instead of calling Google.
    """

    def interest_over_time(
        self,
        keywords: list[str],
        *,
        start_date: str,
        end_date: str,
        geo: str = "",
    ) -> InterestOverTime:
        """Fetch the search-interest series for an explicit past window."""
        ...
