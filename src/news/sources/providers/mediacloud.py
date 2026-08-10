"""Adapter for the MediaCloud ``story-list`` endpoint.

The adapter keeps a local continuation-token cache and a temporary pause so it
can move through pages and handle rate limits cleanly.
"""

from __future__ import annotations

import os
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic

import httpx

from news.sources.base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from news.sources.common import (
    CooldownWindow,
    iso_date_prefix,
    raise_if_cooling,
)
from news.sources.retry import build_timeout, get_with_retry

DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS = 60
MEDIACLOUD_TOKEN_TTL_SECONDS = 900
MEDIACLOUD_TOKEN_MAX_KEYS = 200
MEDIACLOUD_READ_TIMEOUT_SECONDS = 20.0
MEDIACLOUD_PAGE_SIZE = 50


@dataclass(frozen=True, slots=True)
class PaginationTokenEntry:
    """One cached MediaCloud page token."""

    stored_at: float
    token: str


class PaginationTokenStore:
    """Small expiring store for MediaCloud page tokens."""

    def __init__(
        self,
        ttl_seconds: int = MEDIACLOUD_TOKEN_TTL_SECONDS,
        max_keys: int = MEDIACLOUD_TOKEN_MAX_KEYS,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        """Create a bounded token store.

        Parameters
        ----------
        ttl_seconds : int, optional
            Number of seconds a token can be reused.
        max_keys : int, optional
            Maximum number of query keys retained at once.
        clock : Callable[[], float], optional
            Monotonic clock function, injectable for tests.
        """
        self.ttl_seconds = ttl_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._tokens: OrderedDict[
            tuple[object, ...],
            dict[int, PaginationTokenEntry],
        ] = OrderedDict()

    def get(self, key: tuple[object, ...], page: int) -> str:
        """Return an unexpired token for one query and page."""
        self._evict_expired()
        page_tokens = self._tokens.get(key, {})
        entry = page_tokens.get(page)
        if entry is None:
            return ""

        self._tokens.move_to_end(key)
        return entry.token

    def set(self, key: tuple[object, ...], page: int, token: str) -> None:
        """Store the token needed to fetch the next page."""
        if not token:
            return

        self._evict_expired()
        page_tokens = self._tokens.setdefault(key, {})
        page_tokens[page] = PaginationTokenEntry(
            stored_at=self._clock(),
            token=token,
        )
        self._tokens.move_to_end(key)
        while len(self._tokens) > self.max_keys:
            self._tokens.popitem(last=False)

    def _evict_expired(self) -> None:
        """Drop expired query and page tokens."""
        now = self._clock()
        empty_keys: list[tuple[object, ...]] = []
        for key, page_tokens in self._tokens.items():
            expired_pages = [
                page
                for page, entry in page_tokens.items()
                if now - entry.stored_at >= self.ttl_seconds
            ]
            for page in expired_pages:
                page_tokens.pop(page, None)
            if not page_tokens:
                empty_keys.append(key)

        for key in empty_keys:
            self._tokens.pop(key, None)


_PAGINATION_TOKENS = PaginationTokenStore()


class MediaCloudSource(BaseSource):
    """Read story details from the MediaCloud v4 endpoint."""

    name = "mediacloud"
    display_name = "MediaCloud"
    description = "Academic story metadata index (API key required)"

    _BASE_URL = "https://search.mediacloud.org/api/search/story-list"

    def __init__(self) -> None:
        """Initialize the temporary rate-limit state for this adapter."""
        self._cooldown = CooldownWindow()

    def is_available(self) -> bool:
        """Return ``True`` when ``MEDIACLOUD_API_KEY`` is set."""
        return bool(os.getenv("MEDIACLOUD_API_KEY"))

    async def search(
        self,
        options: SourceSearchOptions,
    ) -> SourcePageResult:
        """Read one MediaCloud page of story details."""
        raise_if_cooling(self._cooldown, "MediaCloud")
        api_key = os.getenv("MEDIACLOUD_API_KEY", "")

        headers = {"Authorization": f"Token {api_key}"}
        params = {
            "q": options.query,
            "start": options.start_date,
            "end": options.end_date,
            "platform": "onlinenews-mediacloud",
            "page_size": str(MEDIACLOUD_PAGE_SIZE),
        }

        # Page tokens belong to one query and exist only after the previous page
        # has been requested.
        pagination_key = _build_pagination_key(options)
        pagination_token = (
            _PAGINATION_TOKENS.get(pagination_key, options.page)
            if options.page > 1
            else ""
        )
        if options.page > 1 and not pagination_token:
            raise RuntimeError(
                "MediaCloud pagination token for this page is not cached yet. "
                "Request earlier pages first."
            )
        if pagination_token:
            params["pagination_token"] = pagination_token

        data = await self._fetch_story_list(headers, params)

        raw_stories = data.get("stories") or []
        next_page_token = data.get("pagination_token", "")
        _PAGINATION_TOKENS.set(
            pagination_key,
            options.page + 1,
            next_page_token,
        )
        articles = [self._to_article(s) for s in raw_stories]
        has_more = bool(next_page_token)
        return SourcePageResult(articles=articles, has_more=has_more)

    async def _fetch_story_list(
        self,
        headers: dict[str, str],
        params: dict[str, str],
    ) -> dict:
        """Fetch JSON and turn 429 responses into a local pause."""
        try:
            async with httpx.AsyncClient(
                timeout=build_timeout(
                    read_timeout_seconds=MEDIACLOUD_READ_TIMEOUT_SECONDS
                )
            ) as client:
                response = await get_with_retry(
                    client,
                    self._BASE_URL,
                    headers=headers,
                    params=params,
                    cooldown_check=lambda: raise_if_cooling(
                        self._cooldown,
                        "MediaCloud",
                    ),
                )
                return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                retry_after_seconds = self._cooldown.activate_from_response(
                    exc.response,
                    default_seconds=DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
                )
                raise RuntimeError(
                    "MediaCloud rate limited this query. "
                    f"Pausing for {retry_after_seconds} seconds."
                ) from exc
            raise

    @staticmethod
    def _to_article(raw: dict) -> Article:
        """Convert one MediaCloud story to the common ``Article`` format."""
        return Article(
            title=raw.get("title", ""),
            url=raw.get("url", ""),
            # MediaCloud includes a time component, such as
            # "2024-01-15 00:00:00". Keep only YYYY-MM-DD so sorting and
            # same-day duplicate checks match the other sources.
            date=iso_date_prefix(raw.get("publish_date", "")),
            source="mediacloud",
            domain=raw.get("media_name", ""),
            language=raw.get("language", ""),
        )


def _build_pagination_key(options: SourceSearchOptions) -> tuple[object, ...]:
    """Build a stable key for MediaCloud page tokens."""
    return (
        options.query,
        options.start_date,
        options.end_date,
        options.language,
        options.provider_sort,
        options.include_domains,
        options.exclude_domains,
    )
