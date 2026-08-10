"""Sharing one provider round trip between identical concurrent searches.

Every source enforces a rate limit, so two callers asking the same question at
the same moment must not spend that limit twice. A reloaded browser page and
two commands started together both produce this situation.
"""

from __future__ import annotations

import asyncio
import unittest
from collections.abc import Sequence

from news.search import build_search_request, run_search
from news.sources import SourceQueryReport
from news.sources.base import Article, SourceSearchOptions

PROVIDER_DELAY_SECONDS = 0.05


def _build_request(query: str = "inflation", page: int = 1) -> object:
    """Build one validated search request for these tests."""
    return build_search_request(
        query=query,
        start_date="2026-02-01",
        end_date="2026-02-10",
        source_names=("gdelt",),
        language="",
        deduplicate=False,
        page=page,
    )


class _CountingExecutor:
    """Stand-in source layer that counts how often it is actually called."""

    def __init__(self) -> None:
        self.call_count = 0

    async def __call__(
        self,
        _options: SourceSearchOptions,
        _source_names: Sequence[str] | None,
    ) -> tuple[list[Article], list[SourceQueryReport]]:
        """Return one article after a pause long enough to overlap callers."""
        self.call_count += 1
        await asyncio.sleep(PROVIDER_DELAY_SECONDS)
        reports = [
            SourceQueryReport(
                name="gdelt",
                display_name="GDELT Project",
                available=True,
                requested=True,
                returned=1,
            )
        ]
        articles = [
            Article(
                title="Prices rise",
                url="https://example.com/1",
                date="2026-02-10",
                source="gdelt",
                domain="example.com",
                language="en",
            )
        ]
        return articles, reports


class ConcurrentSearchTests(unittest.IsolatedAsyncioTestCase):
    """Verify which concurrent requests share one provider round trip."""

    async def test_identical_requests_query_the_sources_once(self) -> None:
        """The second caller joins the running search instead of repeating it."""
        executor = _CountingExecutor()
        request = _build_request()

        results = await asyncio.gather(
            run_search(request, executor=executor, use_cache=False),
            run_search(request, executor=executor, use_cache=False),
            run_search(request, executor=executor, use_cache=False),
        )

        self.assertEqual(executor.call_count, 1)
        for result in results:
            self.assertEqual(len(result.articles), 1)
            self.assertEqual(result.meta["returned"], 1)

    async def test_different_requests_still_run_separately(self) -> None:
        """Sharing must be keyed on the request, not applied to everything."""
        executor = _CountingExecutor()

        await asyncio.gather(
            run_search(_build_request("inflation"), executor=executor, use_cache=False),
            run_search(_build_request("employment"), executor=executor, use_cache=False),
            run_search(_build_request("inflation", page=2), executor=executor,
                       use_cache=False),
        )

        self.assertEqual(executor.call_count, 3)

    async def test_each_caller_receives_an_independent_copy(self) -> None:
        """One caller editing its response must not change another's."""
        executor = _CountingExecutor()
        request = _build_request()

        first, second = await asyncio.gather(
            run_search(request, executor=executor, use_cache=False),
            run_search(request, executor=executor, use_cache=False),
        )
        first.articles[0]["title"] = "Edited by the first caller"

        self.assertEqual(second.articles[0]["title"], "Prices rise")

    async def test_a_later_request_runs_again_after_the_first_finishes(self) -> None:
        """Sharing lasts only while a search is in flight, not afterwards."""
        executor = _CountingExecutor()
        request = _build_request()

        await run_search(request, executor=executor, use_cache=False)
        await run_search(request, executor=executor, use_cache=False)

        self.assertEqual(executor.call_count, 2)

    async def test_one_caller_giving_up_does_not_cancel_the_others(self) -> None:
        """A closed browser tab must not fail the searches still waiting."""
        executor = _CountingExecutor()
        request = _build_request()

        staying = asyncio.ensure_future(
            run_search(request, executor=executor, use_cache=False)
        )
        leaving = asyncio.ensure_future(
            run_search(request, executor=executor, use_cache=False)
        )
        # Let both callers reach the shared search before one gives up.
        await asyncio.sleep(0)
        leaving.cancel()

        result = await staying

        self.assertEqual(executor.call_count, 1)
        self.assertEqual(len(result.articles), 1)


if __name__ == "__main__":
    unittest.main()
