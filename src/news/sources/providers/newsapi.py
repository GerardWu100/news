"""NewsAPI Everything source adapter.

This adapter calls ``/v2/everything`` and normalizes returned records into the
shared ``Article`` schema used by downstream filters and exports.
"""

from __future__ import annotations

import os
import re

import httpx

from news.sources.base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from news.sources.common import hostname_from_url, iso_date_prefix
from news.sources.retry import build_timeout, get_with_retry

NEWSAPI_PAGE_SIZE = 50
NEWSAPI_SORT_RELEVANCE = "relevancy"
NEWSAPI_SORT_POPULARITY = "popularity"
NEWSAPI_SORT_PUBLISHED_AT = "publishedAt"
NEWSAPI_SORT_BY_PROVIDER = {
    "relevance": NEWSAPI_SORT_RELEVANCE,
    "popularity": NEWSAPI_SORT_POPULARITY,
}


class NewsApiSource(BaseSource):
    """Adapter for the NewsAPI Everything endpoint."""

    name = "newsapi"
    display_name = "NewsAPI"
    description = "NewsAPI Everything endpoint (API key required)"

    _BASE_URL = "https://newsapi.org/v2/everything"

    def is_available(self) -> bool:
        """Return ``True`` when ``NEWSAPI_API_KEY`` exists in the environment."""
        return bool(os.getenv("NEWSAPI_API_KEY"))

    async def search(self, options: SourceSearchOptions) -> SourcePageResult:
        """Query NewsAPI and normalize the returned article records."""
        api_key = os.getenv("NEWSAPI_API_KEY", "")
        async with httpx.AsyncClient(timeout=build_timeout()) as client:
            response = await get_with_retry(
                client,
                self._BASE_URL,
                headers={"X-Api-Key": api_key},
                params=_build_params(options),
            )

        payload = response.json()
        raw_articles = payload.get("articles") or []
        articles = [
            _to_article(article, requested_language=options.language)
            for article in raw_articles
        ]
        total_results = int(payload.get("totalResults") or 0)
        has_more = options.page * NEWSAPI_PAGE_SIZE < total_results
        return SourcePageResult(articles=articles, has_more=has_more)


def _build_params(options: SourceSearchOptions) -> dict[str, str]:
    """Build one NewsAPI request from normalized search options."""
    params = {
        "q": options.query,
        "from": options.start_date,
        "to": options.end_date,
        "page": str(options.page),
        "pageSize": str(NEWSAPI_PAGE_SIZE),
        "sortBy": NEWSAPI_SORT_BY_PROVIDER.get(
            options.provider_sort,
            NEWSAPI_SORT_PUBLISHED_AT,
        ),
    }

    if options.language:
        params["language"] = options.language
    if options.include_domains:
        params["domains"] = ",".join(options.include_domains)
    if options.exclude_domains:
        params["excludeDomains"] = ",".join(options.exclude_domains)
    if options.newsapi_search_in != "all":
        params["searchIn"] = options.newsapi_search_in

    return params


def _to_article(raw: dict, requested_language: str) -> Article:
    """Convert one NewsAPI article object into the unified ``Article`` schema."""
    url = raw.get("url", "")
    source = raw.get("source") or {}
    return Article(
        title=raw.get("title", ""),
        url=url,
        date=iso_date_prefix(raw.get("publishedAt", "")),
        source="newsapi",
        domain=hostname_from_url(url),
        language=requested_language,
        summary=raw.get("description", "") or "",
        content=_clean_content(raw.get("content", "") or ""),
        section=source.get("name", "") or "",
        author=raw.get("author", "") or "",
    )


def _clean_content(raw_content: str) -> str:
    """Drop NewsAPI truncation markers from the returned content field."""
    return re.sub(r"\s*\[\+\d+\s+chars\]\s*$", "", raw_content).strip()
