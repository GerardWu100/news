"""Core data classes for validated requests and search responses.

The search service uses immutable request objects as cache keys and returns a
structured result that API routes can convert directly to JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """Cleaned and validated inputs for one search request.

    Attributes
    ----------
    query : str
        User-supplied keyword or boolean query string.
    start_date : str
        Inclusive start date in ``YYYY-MM-DD`` format.
    end_date : str
        Inclusive end date in ``YYYY-MM-DD`` format.
    source_names : tuple[str, ...] | None
        Explicit source-name whitelist, or ``None`` for all available sources.
    language : str
        Lowercased language filter passed to providers and local filters.
    deduplicate : bool
        Whether merged provider rows are collapsed by URL/title fingerprints.
    exact_phrase : str
        Optional phrase required by local post-filtering.
    exclude_terms : tuple[str, ...]
        Terms that remove rows during local post-filtering.
    include_domains : tuple[str, ...]
        Domain substrings that rows must include.
    exclude_domains : tuple[str, ...]
        Domain substrings that rows must not include.
    search_scope : str
        Local match scope (``all`` or ``title``).
    match_mode : str
        Local term matching mode (``provider``, ``all_terms``, ``any_term``).
    provider_sort : str
        Source-facing ranking mode.
    section_filters : tuple[str, ...]
        Provider-specific section filter values.
    news_desk_filters : tuple[str, ...]
        New York Times news-desk filter values.
    guardian_tags : tuple[str, ...]
        Guardian tag filter values.
    newsapi_search_in : str
        NewsAPI field scope for keyword matching.
    sort_order : str
        Final merged sort order (``date_desc`` or ``date_asc``).
    page : int
        1-based source page requested by the client.
    """

    query: str
    start_date: str
    end_date: str
    source_names: tuple[str, ...] | None
    language: str
    deduplicate: bool
    exact_phrase: str
    exclude_terms: tuple[str, ...]
    include_domains: tuple[str, ...]
    exclude_domains: tuple[str, ...]
    search_scope: str
    match_mode: str
    provider_sort: str
    section_filters: tuple[str, ...]
    news_desk_filters: tuple[str, ...]
    guardian_tags: tuple[str, ...]
    newsapi_search_in: str
    sort_order: str
    page: int


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Search response before JSON conversion.

    Attributes
    ----------
    articles : list[dict]
        Normalized article records ready for JSON conversion.
    meta : dict
        Request and execution details returned alongside ``articles``.
    """

    articles: list[dict[str, Any]]
    meta: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-ready data used by the API and CLI."""
        return {
            "results": self.articles,
            "meta": self.meta,
        }
