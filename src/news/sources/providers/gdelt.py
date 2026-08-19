"""Adapter for the GDELT Project document-search endpoint."""

from __future__ import annotations

import logging

import httpx

from news.sources.base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from news.sources.retry import build_timeout, get_with_retry

logger = logging.getLogger(__name__)

_GDELT_DATE_LEN = 8
GDELT_PAGE_SIZE = 50
GDELT_SORT_DATE_ASC = "DateAsc"
GDELT_SORT_DATE_DESC = "DateDesc"


class GdeltSource(BaseSource):
    """Read articles from the GDELT Project Document API v2."""

    name = "gdelt"
    display_name = "GDELT Project"
    description = "Open global news article index (no auth required)"

    _BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def is_available(self) -> bool:
        """Return ``True`` because GDELT needs no credentials."""
        return True

    async def search(
        self,
        options: SourceSearchOptions,
    ) -> SourcePageResult:
        """Read one GDELT page of articles."""
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

        async with httpx.AsyncClient(timeout=build_timeout()) as client:
            resp = await get_with_retry(
                client,
                self._BASE_URL,
                params=params,
            )

            content_type = resp.headers.get("content-type", "")
            if "json" not in content_type:
                # GDELT reports refused queries as plain text with HTTP 200,
                # for example the one-request-every-five-seconds rate limit.
                # Returning an empty page here would look like "no articles
                # matched", so raise and let the source report carry the text.
                logger.warning(
                    "GDELT returned non-JSON (%s): %s",
                    content_type,
                    resp.text[:200],
                )
                raise RuntimeError(
                    f"GDELT refused this query: {_first_line(resp.text)}"
                )

            data = resp.json()

        raw_articles = data.get("articles") or []
        articles = [self._to_article(a) for a in raw_articles]
        # This adapter intentionally exposes only the first GDELT page. A full
        # response therefore cannot honestly advertise a page two.
        return SourcePageResult(articles=articles, has_more=False)

    @staticmethod
    def _to_article(raw: dict) -> Article:
        """Convert one GDELT article dictionary to the common format."""
        return Article(
            title=raw.get("title", ""),
            url=raw.get("url", ""),
            date=_format_gdelt_date(raw.get("seendate", "")),
            source="gdelt",
            domain=raw.get("domain", ""),
            language=raw.get("language", ""),
        )


def _first_line(text: str, max_characters: int = 200) -> str:
    """Return the first non-empty line of a provider message, trimmed."""
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:max_characters]
    return "no explanation returned"


def _format_gdelt_date(seen_date: str) -> str:
    """Convert GDELT ``YYYYMMDD...`` timestamps into ``YYYY-MM-DD`` dates."""
    if len(seen_date) < _GDELT_DATE_LEN:
        return ""

    # GDELT returns compact timestamps; store a normal calendar date so all
    # sources sort and filter the same way.
    compact_date = seen_date[:_GDELT_DATE_LEN]
    year = compact_date[:4]
    month = compact_date[4:6]
    day = compact_date[6:8]
    return f"{year}-{month}-{day}"
