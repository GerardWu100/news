"""Adapter for the ACLED conflict event feed endpoint."""

from __future__ import annotations

import os

import httpx

from news.sources.base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from news.sources.retry import build_timeout, get_with_retry

ACLED_PAGE_SIZE = 50


class AcledSource(BaseSource):
    """Adapter for the ACLED conflict-event API."""

    name = "acled"
    display_name = "ACLED"
    description = "Conflict and protest event database (bearer token required)"

    _BASE_URL = "https://acleddata.com/api/acled/read"

    def is_available(self) -> bool:
        """Available when ``ACLED_BEARER_TOKEN`` is set in the environment."""
        return bool(os.getenv("ACLED_BEARER_TOKEN"))

    async def search(
        self,
        options: SourceSearchOptions,
    ) -> SourcePageResult:
        """Query one ACLED page of event records."""
        if options.page > 1:
            return SourcePageResult(articles=[], has_more=False)

        token = os.getenv("ACLED_BEARER_TOKEN", "")

        headers = {"Authorization": f"Bearer {token}"}

        params = {
            "event_date": f"{options.start_date}|{options.end_date}",
            "event_date_where": "BETWEEN",
            "terms": options.query,
            "limit": str(ACLED_PAGE_SIZE),
        }

        async with httpx.AsyncClient(timeout=build_timeout()) as client:
            resp = await get_with_retry(
                client,
                self._BASE_URL,
                headers=headers,
                params=params,
            )
            data = resp.json()

        raw_events = data.get("data") or []
        articles = [self._to_article(e) for e in raw_events]
        has_more = len(raw_events) >= ACLED_PAGE_SIZE
        return SourcePageResult(articles=articles, has_more=has_more)

    @staticmethod
    def _to_article(raw: dict) -> Article:
        """Convert one ACLED event into the shared ``Article`` schema."""
        event_type = raw.get("event_type", "")
        notes = raw.get("notes", "")
        title = f"[{event_type}] {notes}" if event_type else notes

        return Article(
            title=title,
            url=raw.get("source_url", ""),
            date=raw.get("event_date", ""),
            source="acled",
            domain=raw.get("source", ""),
            language="",
        )
