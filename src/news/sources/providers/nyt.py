"""Adapter for the New York Times Article Search API."""

from __future__ import annotations

import os

import httpx

from news.sources.base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from news.sources.common import (
    CooldownWindow,
    hostname_from_url,
    iso_date_prefix,
    raise_if_cooling,
    record_rate_limit_cooldown,
)
from news.sources.retry import build_timeout, get_with_retry

DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 60
NYT_PAGE_SIZE = 10
NYT_SORT_BY_PROVIDER = {
    "newest": "newest",
    "oldest": "oldest",
    "relevance": "relevance",
}


class NewYorkTimesSource(BaseSource):
    """Adapter for the New York Times Article Search API."""

    name = "nyt"
    display_name = "The New York Times"
    description = "New York Times Article Search (API key required)"

    _BASE_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

    def __init__(self) -> None:
        """Initialize transient rate-limit state for this adapter instance."""
        self._cooldown = CooldownWindow()

    def is_available(self) -> bool:
        """Return ``True`` when ``NYT_API_KEY`` exists in the environment."""
        return bool(os.getenv("NYT_API_KEY"))

    async def search(
        self,
        options: SourceSearchOptions,
    ) -> SourcePageResult:
        """Query NYT and normalize the returned documents."""
        raise_if_cooling(self._cooldown, "NYT")
        api_key = os.getenv("NYT_API_KEY", "")
        filter_query = _build_filter_query(options)
        page_number = max(0, options.page - 1)

        async with httpx.AsyncClient(timeout=build_timeout()) as client:
            params = {
                "api-key": api_key,
                "q": options.query,
                "begin_date": options.start_date.replace("-", ""),
                "end_date": options.end_date.replace("-", ""),
                "sort": NYT_SORT_BY_PROVIDER.get(options.provider_sort, "newest"),
                "page": str(page_number),
            }
            if filter_query:
                params["fq"] = filter_query

            try:
                response = await get_with_retry(
                    client,
                    self._BASE_URL,
                    params=params,
                    cooldown_check=lambda: raise_if_cooling(self._cooldown, "NYT"),
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429:
                    raise
                retry_after_seconds = record_rate_limit_cooldown(
                    self._cooldown,
                    exc.response,
                    default_seconds=DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
                )
                raise RuntimeError(
                    "NYT rate limited this query. "
                    f"Try again in {retry_after_seconds} seconds."
                ) from exc

        payload = response.json().get("response", {})
        raw_docs = payload.get("docs") or []
        meta = payload.get("meta") or {}
        articles = [self._to_article(item) for item in raw_docs]
        total_hits = int(meta.get("hits") or 0)
        has_more = options.page * NYT_PAGE_SIZE < total_hits
        return SourcePageResult(articles=articles, has_more=has_more)

    @staticmethod
    def _to_article(raw: dict) -> Article:
        """Convert one NYT document into the shared ``Article`` schema."""
        url = raw.get("web_url", "")
        headline = raw.get("headline") or {}
        byline = raw.get("byline") or {}
        return Article(
            title=headline.get("main", ""),
            url=url,
            date=iso_date_prefix(raw.get("pub_date", "")),
            source="nyt",
            domain=hostname_from_url(url),
            language=raw.get("language", ""),
            summary=raw.get("abstract", "") or raw.get("snippet", ""),
            content=raw.get("lead_paragraph", "") or raw.get("snippet", ""),
            section=raw.get("section_name", ""),
            author=byline.get("original", ""),
        )


def _build_filter_query(options: SourceSearchOptions) -> str:
    """Build a NYT ``fq`` string from section and desk filters."""
    clauses: list[str] = []
    if options.section_filters:
        clauses.append(_format_fq_values("section_name", options.section_filters))
    if options.news_desk_filters:
        clauses.append(_format_fq_values("news_desk", options.news_desk_filters))
    return " AND ".join(clauses)


def _format_fq_values(field_name: str, values: tuple[str, ...]) -> str:
    """Format one NYT filter query clause with quoted values."""
    quoted_values = " ".join(f'"{_escape_filter_value(value)}"' for value in values)
    return f"{field_name}:({quoted_values})"


def _escape_filter_value(value: str) -> str:
    """Escape double quotes within one NYT filter value."""
    return value.replace('"', '\\"')
