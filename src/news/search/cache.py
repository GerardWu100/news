"""In-memory time-to-live cache for validated search requests.

The cache stores full ``SearchResult`` objects keyed by immutable
``SearchRequest`` values. It reduces repeated upstream fan-out for identical
queries, expires entries by wall-clock age, and evicts oldest live rows when
capacity limits are reached.
"""

from __future__ import annotations

import copy
from collections import OrderedDict
from time import monotonic
from typing import Callable

from news.web.config import read_config

from .models import SearchRequest, SearchResult

DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_CACHE_MAX_ENTRIES = 100


class SearchResultCache:
    """TTL cache keyed by the fully validated ``SearchRequest`` object."""

    def __init__(
        self,
        ttl_seconds: int,
        max_entries: int,
        *,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        """Create a cache with explicit lifetime and capacity limits."""
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self._clock = clock
        self._entries: OrderedDict[SearchRequest, tuple[float, SearchResult]] = (
            OrderedDict()
        )

    def get(self, request: SearchRequest) -> SearchResult | None:
        """Return a deep-copied cached result if the entry is still fresh."""
        self._evict_expired()
        entry = self._entries.get(request)
        if entry is None:
            return None

        stored_at, result = entry
        if self._clock() - stored_at >= self.ttl_seconds:
            self._entries.pop(request, None)
            return None

        self._entries.move_to_end(request)
        return copy.deepcopy(result)

    def set(self, request: SearchRequest, result: SearchResult) -> None:
        """Store a deep copy of the result and enforce the size limit."""
        self._evict_expired()
        self._entries[request] = (self._clock(), copy.deepcopy(result))
        self._entries.move_to_end(request)

        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def clear(self) -> None:
        """Remove all cached entries."""
        self._entries.clear()

    @property
    def entry_count(self) -> int:
        """Return the current number of live cache entries."""
        self._evict_expired()
        return len(self._entries)

    def _evict_expired(self) -> None:
        """Drop expired entries in insertion order."""
        now = self._clock()
        expired_keys = [
            request
            for request, (stored_at, _) in self._entries.items()
            if now - stored_at >= self.ttl_seconds
        ]
        for request in expired_keys:
            self._entries.pop(request, None)


def build_default_search_cache() -> SearchResultCache:
    """Construct the process-wide cache from ``config.toml`` defaults."""
    ttl_seconds, max_entries = _read_cache_config()
    return SearchResultCache(
        ttl_seconds=ttl_seconds,
        max_entries=max_entries,
    )


def _read_cache_config() -> tuple[int, int]:
    """Read cache settings from ``config.toml`` with safe fallbacks."""
    cache_config = read_config().get("cache", {})
    ttl_seconds = _coerce_positive_int(
        cache_config.get("ttl_seconds"),
        DEFAULT_CACHE_TTL_SECONDS,
    )
    max_entries = _coerce_positive_int(
        cache_config.get("max_entries"),
        DEFAULT_CACHE_MAX_ENTRIES,
    )
    return ttl_seconds, max_entries


def _coerce_positive_int(value: object, default: int) -> int:
    """Convert config values to positive integers with a fallback."""
    if isinstance(value, int) and value > 0:
        return value
    return default
