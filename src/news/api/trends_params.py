"""Read HTTP query parameters for the trends route.

The parameters deliberately mirror the search route: the same ``q``, ``start``,
and ``end`` a caller already sends for articles produce the matching attention
series, so a browser can pass its existing form values through unchanged.
"""

from __future__ import annotations

from fastapi import Query

from news.trends.keywords import MAX_KEYWORDS


class TrendsQueryParams:
    """Container for the public trends query parameters."""

    def __init__(
        self,
        q: str = Query(
            ...,
            description=(
                "The same keyword query used for article search. Boolean "
                "operators and excluded terms are removed, quoted phrases are "
                f"kept whole, and at most {MAX_KEYWORDS} keywords are used."
            ),
        ),
        start: str = Query(..., description="Inclusive window start (YYYY-MM-DD)"),
        end: str = Query(..., description="Inclusive window end (YYYY-MM-DD)"),
        geo: str = Query(
            default="",
            description=(
                "Geography code such as US or US-NY. Empty uses the configured "
                "default, which is worldwide unless changed."
            ),
        ),
        as_of: str = Query(
            default="",
            description=(
                "Optional decision date (YYYY-MM-DD) inside the window. When "
                "given, later points are dropped and the series is rescaled to "
                "the highest value up to that date, removing the future peak "
                "that Google's own scaling would otherwise encode."
            ),
        ),
    ) -> None:
        self.q = q
        self.start = start
        self.end = end
        self.geo = geo
        self.as_of = as_of
