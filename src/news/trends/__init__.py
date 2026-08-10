"""Public import surface for the Google Trends package.

Callers import the ``TrendsClient`` interface and data models from here and
the production ``GoogleTrendsClient`` for construction at the application
boundary. Conversion internals stay private to ``news.trends.google``.
"""

from .google import GoogleTrendsClient
from .models import (
    InterestByRegion,
    InterestOverTime,
    RegionInterest,
    RelatedQueries,
    RelatedQuery,
    TrendsClient,
    TrendsFetchError,
    TrendsValidationError,
)

__all__ = [
    "GoogleTrendsClient",
    "InterestByRegion",
    "InterestOverTime",
    "RegionInterest",
    "RelatedQueries",
    "RelatedQuery",
    "TrendsClient",
    "TrendsFetchError",
    "TrendsValidationError",
]
