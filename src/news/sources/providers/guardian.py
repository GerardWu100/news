"""Adapter for the Guardian Open Platform content search endpoint.

The adapter queries Guardian article metadata and optional rich text fields,
then maps each record into the shared ``Article`` model.
"""

from __future__ import annotations

import html
import os
import re

import httpx

from news.sources.base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from news.sources.common import hostname_from_url, iso_date_prefix
from news.sources.retry import build_timeout, get_with_retry

GUARDIAN_PAGE_SIZE = 50
MAX_CONTEXT_CHARS = 4000
GUARDIAN_ORDER_BY_PROVIDER = frozenset({"newest", "oldest", "relevance"})


class GuardianSource(BaseSource):
    """Adapter for the Guardian content search endpoint."""

    name = "guardian"
    display_name = "The Guardian"
    description = "Guardian Open Platform article search (API key required)"

    _BASE_URL = "https://content.guardianapis.com/search"

    def is_available(self) -> bool:
        """Return ``True`` when ``GUARDIAN_API_KEY`` exists in the environment."""
        return bool(os.getenv("GUARDIAN_API_KEY"))

    async def search(
        self,
        options: SourceSearchOptions,
    ) -> SourcePageResult:
        """Query the Guardian API and normalize the returned article records."""
        api_key = os.getenv("GUARDIAN_API_KEY", "")
        async with httpx.AsyncClient(timeout=build_timeout()) as client:
            params = {
                "api-key": api_key,
                "q": options.query,
                "from-date": options.start_date,
                "to-date": options.end_date,
                "page-size": str(GUARDIAN_PAGE_SIZE),
                "page": str(options.page),
                "show-fields": "lang,trailText,standfirst,body,byline",
            }
            if options.language:
                params["lang"] = options.language
            if options.section_filters:
                params["section"] = ",".join(options.section_filters)
            if options.guardian_tags:
                params["tag"] = ",".join(options.guardian_tags)

            if options.provider_sort in GUARDIAN_ORDER_BY_PROVIDER:
                params["order-by"] = options.provider_sort

            response = await get_with_retry(
                client,
                self._BASE_URL,
                params=params,
            )

        payload = response.json().get("response") or {}
        raw_results = payload.get("results") or []
        articles = [self._to_article(item) for item in raw_results]
        current_page = int(payload.get("currentPage") or options.page)
        total_pages = int(payload.get("pages") or current_page)
        has_more = current_page < total_pages
        return SourcePageResult(articles=articles, has_more=has_more)

    @staticmethod
    def _to_article(raw: dict) -> Article:
        """Convert one Guardian result object into the unified ``Article``."""
        fields = raw.get("fields") or {}
        url = raw.get("webUrl", "")
        return Article(
            title=raw.get("webTitle", ""),
            url=url,
            date=iso_date_prefix(raw.get("webPublicationDate", "")),
            source="guardian",
            domain=hostname_from_url(url),
            language=fields.get("lang", ""),
            summary=_compact_text(
                fields.get("trailText", "") or fields.get("standfirst", "")
            ),
            content=_compact_text(fields.get("body", "")),
            section=raw.get("sectionName", ""),
            author=_compact_text(fields.get("byline", "")),
        )


def _compact_text(raw_html: str) -> str:
    """Strip HTML and trim long Guardian text fields for the API payload."""
    if not raw_html:
        return ""

    without_tags = re.sub(r"<[^>]+>", " ", raw_html)
    normalized = re.sub(r"\s+", " ", html.unescape(without_tags)).strip()
    return normalized[:MAX_CONTEXT_CHARS]
