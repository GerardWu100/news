"""Deterministic Google Trends fixtures shared by API and CLI tests."""

from __future__ import annotations

from news.trends import (
    InterestByRegion,
    InterestOverTime,
    RegionInterest,
    RelatedQueries,
    RelatedQuery,
)

FIXED_FETCHED_AT = "2026-08-09T12:00:00+00:00"


def build_interest_over_time(keywords: tuple[str, ...]) -> InterestOverTime:
    """Return a two-point series for the requested keywords."""
    return InterestOverTime(
        keywords=keywords,
        timeframe="today 3-m",
        geo="US",
        dates=("2026-08-01", "2026-08-02"),
        is_partial=(False, True),
        values={keyword: (40, 60) for keyword in keywords},
        fetched_at=FIXED_FETCHED_AT,
    )


def build_interest_by_region(keywords: tuple[str, ...]) -> InterestByRegion:
    """Return a two-region breakdown for the requested keywords."""
    return InterestByRegion(
        keywords=keywords,
        timeframe="today 3-m",
        geo="US",
        resolution="REGION",
        regions=(
            RegionInterest(region="New York", values=dict.fromkeys(keywords, 100)),
            RegionInterest(region="Texas", values=dict.fromkeys(keywords, 55)),
        ),
        fetched_at=FIXED_FETCHED_AT,
    )


def build_related_queries(keyword: str) -> RelatedQueries:
    """Return one top and one rising related query for the keyword."""
    return RelatedQueries(
        keyword=keyword,
        timeframe="today 3-m",
        geo="US",
        top=(RelatedQuery(query=f"{keyword} price", value=100),),
        rising=(RelatedQuery(query=f"{keyword} crash", value=250),),
        fetched_at=FIXED_FETCHED_AT,
    )


class FakeTrendsClient:
    """Offline ``TrendsClient`` returning the fixtures above."""

    def interest_over_time(
        self,
        keywords: list[str],
        *,
        timeframe: str,
        geo: str,
    ) -> InterestOverTime:
        """Return the deterministic series fixture."""
        return build_interest_over_time(tuple(keywords))

    def interest_by_region(
        self,
        keywords: list[str],
        *,
        timeframe: str,
        geo: str,
        resolution: str,
    ) -> InterestByRegion:
        """Return the deterministic regional fixture."""
        return build_interest_by_region(tuple(keywords))

    def related_queries(
        self,
        keyword: str,
        *,
        timeframe: str,
        geo: str,
    ) -> RelatedQueries:
        """Return the deterministic related-queries fixture."""
        return build_related_queries(keyword)
