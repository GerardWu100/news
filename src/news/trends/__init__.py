"""Search-attention data for the same historical window as a news search.

The project retrieves news published inside an explicit past window. This
package adds one matching signal: how much the public searched for the same
keywords during those same days. Articles say what was published; Trends says
what people were looking for, including things the press had not covered yet.

Public objects:

``keywords_from_query``
    Turn a news search query into plain Trends keywords.
``GoogleTrendsClient``
    Fetch the series for an explicit window, spacing requests so Google's rate
    limit is not tripped.
``rebase_as_of``
    Rescale a fetched series to the information available on one date, which
    removes the look-ahead effect built into Google's 0-100 index.

The capability review behind these choices, including which Google functions
still work, is ``docs/html/google_trends_capabilities.html``.
"""

from news.trends.google import GoogleTrendsClient
from news.trends.keywords import MAX_KEYWORDS, keywords_from_query
from news.trends.models import (
    InterestOverTime,
    TrendsClient,
    TrendsFetchError,
    TrendsValidationError,
)
from news.trends.pacing import RequestPacer
from news.trends.rebase import rebase_as_of
from news.trends.window import TrendsWindow, build_trends_window

__all__ = [
    "MAX_KEYWORDS",
    "GoogleTrendsClient",
    "InterestOverTime",
    "RequestPacer",
    "TrendsClient",
    "TrendsFetchError",
    "TrendsValidationError",
    "TrendsWindow",
    "build_trends_window",
    "keywords_from_query",
    "rebase_as_of",
]
