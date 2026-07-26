"""Tests for search orchestration, provider options, and result metadata."""

from __future__ import annotations

from collections.abc import Sequence
import unittest

from news.search import build_search_request, run_search
from news.sources import SourceQueryReport
from news.sources.base import Article, SourceSearchOptions


class RunSearchTests(unittest.IsolatedAsyncioTestCase):
    """Check end-to-end behavior of the pure search pipeline."""

    async def test_run_search_builds_meta_and_applies_filters(self) -> None:
        """Language filtering and deduplication should be reflected in meta."""
        request = build_search_request(
            query="chip demand",
            start_date="2026-02-01",
            end_date="2026-02-10",
            source_names=("gdelt", "mediacloud"),
            language="en",
            deduplicate=True,
            exact_phrase="chip demand",
            domain_filter="example.com",
            match_mode="all_terms",
            search_scope="title",
            sort_order="date_desc",
            page=1,
        )

        async def fake_executor(
            _options: SourceSearchOptions,
            _source_names: Sequence[str] | None,
        ) -> tuple[list[Article], list[SourceQueryReport]]:
            """Return mixed articles so filtering and deduplication are visible."""
            reports = [
                SourceQueryReport(
                    name="gdelt",
                    display_name="GDELT Project",
                    available=True,
                    requested=True,
                    returned=2,
                ),
                SourceQueryReport(
                    name="mediacloud",
                    display_name="MediaCloud",
                    available=True,
                    requested=True,
                    returned=1,
                ),
            ]
            articles = [
                Article(
                    title="Chip demand rises",
                    url="https://example.com/chips?id=1&utm_source=feed",
                    date="2026-02-10",
                    source="gdelt",
                    domain="example.com",
                    language="en",
                ),
                Article(
                    title="Chip demand rises",
                    url="https://www.example.com/chips?id=1",
                    date="2026-02-10",
                    source="mediacloud",
                    domain="Example.com",
                    language="english",
                ),
                Article(
                    title="Mercado de chips",
                    url="https://example.com/es?id=9",
                    date="2026-02-09",
                    source="gdelt",
                    domain="example.com",
                    language="es",
                ),
            ]
            return articles, reports

        result = await run_search(request, executor=fake_executor)

        self.assertEqual(len(result.articles), 1)
        self.assertEqual(result.meta["total"], 1)
        self.assertEqual(result.meta["total_before_deduplication"], 2)
        self.assertEqual(result.meta["duplicates_removed"], 1)
        self.assertEqual(result.meta["requested_sources"], ["gdelt", "mediacloud"])
        self.assertEqual(result.meta["include_domains"], ["example.com"])
        self.assertEqual(result.articles[0]["duplicate_count"], 2)
        self.assertEqual(
            result.articles[0]["matched_sources"],
            ["gdelt", "mediacloud"],
        )

    async def test_run_search_passes_provider_options_to_executor(self) -> None:
        """Provider-aware filters should reach the source fan-out layer."""
        request = build_search_request(
            query="inflation",
            start_date="2026-02-01",
            end_date="2026-02-10",
            source_names=("guardian", "nyt", "newsapi"),
            language="en",
            deduplicate=True,
            domain_filter="ft.com",
            exclude_domains="reddit.com",
            provider_sort="relevance",
            section="business",
            news_desk="Business Day",
            guardian_tag="business/economics",
            newsapi_search_in="title,content",
        )
        captured: dict[str, object] = {}

        async def fake_executor(
            options: SourceSearchOptions,
            source_names: Sequence[str] | None,
        ) -> tuple[list[Article], list[SourceQueryReport]]:
            """Capture provider-facing options without querying live sources."""
            captured["options"] = options
            captured["source_names"] = source_names
            return [], []

        await run_search(request, executor=fake_executor)

        options = captured["options"]
        self.assertEqual(captured["source_names"], ("guardian", "nyt", "newsapi"))
        self.assertEqual(options.page, 1)
        self.assertEqual(options.provider_sort, "relevance")
        self.assertEqual(options.include_domains, ("ft.com",))
        self.assertEqual(options.exclude_domains, ("reddit.com",))
        self.assertEqual(options.section_filters, ("business",))
        self.assertEqual(options.news_desk_filters, ("Business Day",))
        self.assertEqual(options.guardian_tags, ("business/economics",))
        self.assertEqual(options.newsapi_search_in, "title,content")

    async def test_run_search_filters_one_provider_page(self) -> None:
        """One provider-page response should still honor local filters."""
        request = build_search_request(
            query="market rally",
            start_date="2026-02-01",
            end_date="2026-02-10",
            source_names=("gdelt",),
            language="",
            deduplicate=False,
            exclude_terms="crypto",
            match_mode="any_term",
            search_scope="all",
            sort_order="date_desc",
            page=2,
        )

        async def fake_executor(
            _options: SourceSearchOptions,
            _source_names: Sequence[str] | None,
        ) -> tuple[list[Article], list[SourceQueryReport]]:
            """Return one provider page that still needs local post-filtering."""
            reports = [
                SourceQueryReport(
                    name="gdelt",
                    display_name="GDELT Project",
                    available=True,
                    requested=True,
                    returned=4,
                    has_more=True,
                )
            ]
            articles = [
                Article(
                    title="Market rally extends",
                    url="https://example.com/1",
                    date="2026-02-10",
                    source="gdelt",
                    domain="example.com",
                    language="en",
                ),
                Article(
                    title="Crypto rally extends",
                    url="https://example.com/2",
                    date="2026-02-09",
                    source="gdelt",
                    domain="example.com",
                    language="en",
                ),
                Article(
                    title="Bond market rally cools",
                    url="https://example.com/3",
                    date="2026-02-08",
                    source="gdelt",
                    domain="example.com",
                    language="en",
                ),
                Article(
                    title="Global market rebound",
                    url="https://example.com/4",
                    date="2026-02-07",
                    source="gdelt",
                    domain="example.com",
                    language="en",
                ),
            ]
            return articles, reports

        result = await run_search(request, executor=fake_executor)

        self.assertEqual(result.meta["total"], 3)
        self.assertEqual(result.meta["returned"], 3)
        self.assertTrue(result.meta["has_more"])
        self.assertTrue(result.meta["has_previous"])
        self.assertEqual(len(result.articles), 3)
        self.assertEqual(result.articles[-1]["title"], "Global market rebound")

    async def test_run_search_uses_source_report_has_more_flag(self) -> None:
        """Merged pagination state should come from provider pagination state."""
        request = build_search_request(
            query="policy",
            start_date="2026-02-01",
            end_date="2026-02-20",
            source_names=("gdelt", "guardian"),
            language="",
            deduplicate=False,
            page=3,
        )

        async def fake_executor(
            options: SourceSearchOptions,
            source_names: Sequence[str] | None,
        ) -> tuple[list[Article], list[SourceQueryReport]]:
            """Return source reports with mixed pagination state."""
            self.assertEqual(options.page, 3)
            self.assertEqual(source_names, ("gdelt", "guardian"))
            reports = [
                SourceQueryReport(
                    name="gdelt",
                    display_name="GDELT Project",
                    available=True,
                    requested=True,
                    returned=0,
                    has_more=False,
                ),
                SourceQueryReport(
                    name="guardian",
                    display_name="The Guardian",
                    available=True,
                    requested=True,
                    returned=1,
                    has_more=True,
                ),
            ]
            return [
                Article(
                    title="Policy story 3",
                    url="https://example.com/3",
                    date="2026-02-18",
                    source="guardian",
                    domain="example.com",
                    language="en",
                )
            ], reports

        result = await run_search(request, executor=fake_executor)

        self.assertTrue(result.meta["has_more"])
        self.assertTrue(result.meta["has_previous"])
        self.assertEqual(result.meta["returned"], 1)
