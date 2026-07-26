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

from news.web.config import CacheSettings

from .models import SearchRequest, SearchResult

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
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
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


def build_search_cache(settings: CacheSettings) -> SearchResultCache:
    """Construct a search cache from validated application settings."""
    return SearchResultCache(
        ttl_seconds=settings.ttl_seconds,
        max_entries=settings.max_entries,
    )
