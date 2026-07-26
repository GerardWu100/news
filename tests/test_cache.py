"""Regression tests for the in-memory search result cache."""

from __future__ import annotations

import unittest
from collections.abc import Sequence
from inspect import signature

from news.search.cache import SearchResultCache
from news.search.models import SearchRequest, SearchResult
from news.search.service import run_search
from news.sources import SourceQueryReport
from news.sources.base import Article, SourceSearchOptions


class _ManualClock:
    """Simple mutable clock for TTL tests."""

    def __init__(self) -> None:
        self.current = 0.0

    def __call__(self) -> float:
        return self.current


def _build_request(query: str) -> SearchRequest:
    """Create a compact request object for cache tests."""
    return SearchRequest(
        query=query,
        start_date="2026-03-01",
        end_date="2026-03-05",
        source_names=("guardian",),
        language="en",
        deduplicate=True,
        exact_phrase="",
        exclude_terms=(),
        include_domains=(),
        exclude_domains=(),
        search_scope="all",
        match_mode="provider",
        provider_sort="default",
        section_filters=(),
        news_desk_filters=(),
        guardian_tags=(),
        newsapi_search_in="all",
        sort_order="date_desc",
        page=1,
    )


def _build_result(title: str) -> SearchResult:
    """Create a minimal search result object for cache tests."""
    return SearchResult(
        articles=[
            {
                "title": title,
                "url": "https://example.com/story",
                "date": "2026-03-05",
                "source": "guardian",
                "matched_sources": ["guardian"],
                "duplicate_count": 1,
            }
        ],
        meta={
            "query": title,
            "start": "2026-03-01",
            "end": "2026-03-05",
            "language": "en",
            "deduplicate": True,
            "exact_phrase": "",
            "exclude_terms": [],
            "include_domains": [],
            "exclude_domains": [],
            "search_scope": "all",
            "match_mode": "provider",
            "provider_sort": "default",
            "section_filters": [],
            "news_desk_filters": [],
            "guardian_tags": [],
            "newsapi_search_in": "all",
            "sort_order": "date_desc",
            "page": 1,
            "has_more": False,
            "has_previous": False,
            "returned": 1,
            "requested_sources": ["guardian"],
            "total": 1,
            "total_before_deduplication": 1,
            "duplicates_removed": 0,
            "source_reports": [],
        },
    )


class SearchResultCacheTests(unittest.TestCase):
    """Test TTL expiry and LRU eviction behavior."""

    def test_cache_entry_expires_after_ttl(self) -> None:
        """Expired entries should not be returned."""
        clock = _ManualClock()
        cache = SearchResultCache(ttl_seconds=5, max_entries=2, clock=clock)
        request = _build_request("fed")

        cache.set(request, _build_result("fed"))
        self.assertIsNotNone(cache.get(request))

        clock.current = 6.0
        self.assertIsNone(cache.get(request))

    def test_cache_evicts_oldest_entry_when_full(self) -> None:
        """The oldest live cache entry should be evicted at capacity."""
        clock = _ManualClock()
        cache = SearchResultCache(ttl_seconds=60, max_entries=2, clock=clock)
        request_one = _build_request("fed")
        request_two = _build_request("inflation")
        request_three = _build_request("rates")

        cache.set(request_one, _build_result("fed"))
        clock.current = 1.0
        cache.set(request_two, _build_result("inflation"))
        clock.current = 2.0
        cache.set(request_three, _build_result("rates"))

        self.assertIsNone(cache.get(request_one))
        self.assertIsNotNone(cache.get(request_two))
        self.assertIsNotNone(cache.get(request_three))


class RunSearchCacheIntegrationTests(unittest.IsolatedAsyncioTestCase):
    """Test that ``run_search`` reuses cached results for identical requests."""

    def test_run_search_cache_default_is_explicit_inside_function(self) -> None:
        """The function signature should not bind a mutable cache singleton."""
        cache_parameter = signature(run_search).parameters["cache"]

        self.assertIsNone(cache_parameter.default)

    async def test_run_search_uses_cache_before_executor(self) -> None:
        """A repeated request should not hit the executor twice."""
        cache = SearchResultCache(ttl_seconds=60, max_entries=10)
        request = _build_request("fed")
        call_count = 0

        async def fake_executor(
            _options: SourceSearchOptions,
            _source_names: Sequence[str] | None,
        ) -> tuple[list[Article], list[SourceQueryReport]]:
            """Return one article while counting real executor calls."""
            nonlocal call_count
            call_count += 1
            return (
                [
                    Article(
                        title="Fed holds rates steady",
                        url="https://example.com/fed",
                        date="2026-03-05",
                        source="guardian",
                        domain="example.com",
                        language="en",
                    )
                ],
                [
                    SourceQueryReport(
                        name="guardian",
                        display_name="The Guardian",
                        available=True,
                        requested=True,
                        returned=1,
                    )
                ],
            )

        first = await run_search(request, executor=fake_executor, cache=cache)
        second = await run_search(request, executor=fake_executor, cache=cache)

        self.assertEqual(call_count, 1)
        self.assertEqual(first.articles, second.articles)


if __name__ == "__main__":
    unittest.main()
