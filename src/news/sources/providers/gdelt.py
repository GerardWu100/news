"""Adapter for the GDELT Project document search endpoint."""

from __future__ import annotations

import logging

import httpx

from news.sources.base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from news.sources.retry import build_timeout, get_with_retry

logger = logging.getLogger(__name__)

_GDELT_DATE_LEN = 8
GDELT_PAGE_SIZE = 50
GDELT_READ_TIMEOUT_SECONDS = 20.0
GDELT_SORT_DATE_ASC = "DateAsc"
GDELT_SORT_DATE_DESC = "DateDesc"


class GdeltSource(BaseSource):
    """Adapter for the GDELT Project Document API v2."""

    name = "gdelt"
    display_name = "GDELT Project"
    description = "Open global news article index (no auth required)"

    _BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def is_available(self) -> bool:
        """Always available -- GDELT requires no credentials."""
        return True

    async def search(
        self,
        options: SourceSearchOptions,
    ) -> SourcePageResult:
        """Query one GDELT page of articles."""
        gdelt_start = options.start_date.replace("-", "") + "000000"
        gdelt_end = options.end_date.replace("-", "") + "235959"

        if options.page > 1:
            return SourcePageResult(articles=[], has_more=False)

        params = {
            "query": options.query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(GDELT_PAGE_SIZE),
            "sort": (
                GDELT_SORT_DATE_ASC
                if options.provider_sort == "oldest"
                else GDELT_SORT_DATE_DESC
            ),
            "startdatetime": gdelt_start,
            "enddatetime": gdelt_end,
        }

        async with httpx.AsyncClient(
            timeout=build_timeout(read_timeout_seconds=GDELT_READ_TIMEOUT_SECONDS)
        ) as client:
            resp = await get_with_retry(
                client,
                self._BASE_URL,
                params=params,
            )

            content_type = resp.headers.get("content-type", "")
            if "json" not in content_type:
                logger.warning(
                    "GDELT returned non-JSON (%s): %s",
                    content_type,
                    resp.text[:200],
                )
                return SourcePageResult(articles=[], has_more=False)

            data = resp.json()

        raw_articles = data.get("articles") or []
        articles = [self._to_article(a) for a in raw_articles]
        has_more = len(raw_articles) >= GDELT_PAGE_SIZE
        return SourcePageResult(articles=articles, has_more=has_more)

    @staticmethod
    def _to_article(raw: dict) -> Article:
        """Convert one GDELT article dict into the shared ``Article`` schema."""
        return Article(
            title=raw.get("title", ""),
            url=raw.get("url", ""),
            date=_format_gdelt_date(raw.get("seendate", "")),
            source="gdelt",
            domain=raw.get("domain", ""),
            language=raw.get("language", ""),
        )


def _format_gdelt_date(seen_date: str) -> str:
    """Convert GDELT ``YYYYMMDD...`` timestamps into ``YYYY-MM-DD`` dates."""
    if len(seen_date) < _GDELT_DATE_LEN:
        return ""

    # GDELT returns compact timestamps; the project stores normalized article
    # dates as ISO calendar strings for shared sorting and filtering.
    compact_date = seen_date[:_GDELT_DATE_LEN]
    year = compact_date[:4]
    month = compact_date[4:6]
    day = compact_date[6:8]
    return f"{year}-{month}-{day}"
