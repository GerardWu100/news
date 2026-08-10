"""Data models, errors, and the client interface for Google Trends data.

Google Trends returns relative search-interest data, not articles, so these
models are independent from the ``Article`` search schema. Every value is
Google's 0-100 index: 100 marks the highest interest within the requested
window, and all other values are scaled to that peak. Absolute search counts
are never available.

Each result records ``fetched_at`` because Google samples the underlying data;
two fetches of the same window can return slightly different values, so stored
results are only reproducible together with their fetch timestamp.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol


class TrendsValidationError(ValueError):
    """Raised when trends request inputs are invalid before any network call."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TrendsFetchError(RuntimeError):
    """Raised when Google Trends rejects or fails an upstream request."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True, slots=True)
class InterestOverTime:
    """Search-interest time series for up to five keywords.

    Attributes
    ----------
    keywords : tuple[str, ...]
        Requested keywords; values are scaled relative to the highest point
        across all of them combined.
    timeframe : str
        Google timeframe expression, for example ``today 12-m`` or
        ``2025-01-01 2025-06-30``.
    geo : str
        Geography code (``""`` worldwide, ``US`` country, ``US-NY`` state).
    dates : tuple[str, ...]
        One label per point. Google chooses granularity from the window
        length: roughly daily under nine months, weekly under five years,
        monthly beyond that.
    is_partial : tuple[bool, ...]
        Aligned with ``dates``; ``True`` marks a still-accumulating period
        (usually the most recent point) whose value will change.
    values : dict[str, tuple[int, ...]]
        Keyword to its series, aligned with ``dates``.
    fetched_at : str
        UTC timestamp of the fetch in ISO format.
    """

    keywords: tuple[str, ...]
    timeframe: str
    geo: str
    dates: tuple[str, ...]
    is_partial: tuple[bool, ...]
    values: dict[str, tuple[int, ...]]
    fetched_at: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly ``dict``."""
        data = asdict(self)
        data["keywords"] = list(self.keywords)
        data["dates"] = list(self.dates)
        data["is_partial"] = list(self.is_partial)
        data["values"] = {kw: list(series) for kw, series in self.values.items()}
        return data


@dataclass(frozen=True, slots=True)
class RegionInterest:
    """Search interest for one region within a regional breakdown."""

    region: str
    values: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly ``dict``."""
        return {"region": self.region, "values": dict(self.values)}


@dataclass(frozen=True, slots=True)
class InterestByRegion:
    """Regional search-interest breakdown for up to five keywords.

    ``resolution`` controls granularity: ``COUNTRY``, ``REGION``
    (state/province), ``CITY``, or ``DMA`` (United States metro areas).
    Regions with too little volume are omitted by Google, not returned as
    zero.
    """

    keywords: tuple[str, ...]
    timeframe: str
    geo: str
    resolution: str
    regions: tuple[RegionInterest, ...]
    fetched_at: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly ``dict``."""
        return {
            "keywords": list(self.keywords),
            "timeframe": self.timeframe,
            "geo": self.geo,
            "resolution": self.resolution,
            "regions": [row.to_dict() for row in self.regions],
            "fetched_at": self.fetched_at,
        }


@dataclass(frozen=True, slots=True)
class RelatedQuery:
    """One query Google associates with the requested keyword.

    ``value`` means different things per list: in the ``top`` list it is the
    0-100 relative volume index; in the ``rising`` list it is percent growth
    against the prior period, where Google reports extreme growth (over
    roughly 5000 percent) with a very large number shown as "Breakout" on the
    website.
    """

    query: str
    value: int

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly ``dict``."""
        return {"query": self.query, "value": self.value}


@dataclass(frozen=True, slots=True)
class RelatedQueries:
    """Top and rising related queries for one keyword."""

    keyword: str
    timeframe: str
    geo: str
    top: tuple[RelatedQuery, ...]
    rising: tuple[RelatedQuery, ...]
    fetched_at: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly ``dict``."""
        return {
            "keyword": self.keyword,
            "timeframe": self.timeframe,
            "geo": self.geo,
            "top": [row.to_dict() for row in self.top],
            "rising": [row.to_dict() for row in self.rising],
            "fetched_at": self.fetched_at,
        }


class TrendsClient(Protocol):
    """Interface the API and CLI depend on instead of a concrete library.

    ``GoogleTrendsClient`` is the production implementation; tests supply
    offline fakes. Keeping callers on this interface makes replacing the
    underlying library a one-module change if it stops working.
    """

    def interest_over_time(
        self,
        keywords: list[str],
        *,
        timeframe: str,
        geo: str,
    ) -> InterestOverTime:
        """Fetch the 0-100 interest series for up to five keywords."""
        ...

    def interest_by_region(
        self,
        keywords: list[str],
        *,
        timeframe: str,
        geo: str,
        resolution: str,
    ) -> InterestByRegion:
        """Fetch the regional interest breakdown for up to five keywords."""
        ...

    def related_queries(
        self,
        keyword: str,
        *,
        timeframe: str,
        geo: str,
    ) -> RelatedQueries:
        """Fetch top and rising related queries for one keyword."""
        ...
