"""Regression tests for search validation, orchestration, and adapters."""

from __future__ import annotations

import unittest
from collections.abc import Sequence
from unittest.mock import AsyncMock, patch

import httpx

from news.search import (
    build_search_request,
    canonicalize_url,
    deduplicate_articles,
    run_search,
)
from news.search.errors import SearchValidationError
from news.search.filters import filter_by_language, sort_articles
from news.search.validation import split_csv_values
from news.sources import SourceQueryReport
from news.sources.base import Article, SourceSearchOptions
from news.sources.providers.guardian import GuardianSource
from news.sources.providers.mediacloud import MediaCloudSource
from news.sources.providers.newsapi import _build_params as build_newsapi_params
from news.sources.providers.newsapi import _to_article as newsapi_to_article
from news.sources.providers.nyt import NewYorkTimesSource


class BuildSearchRequestTests(unittest.TestCase):
    """Validate request normalization and error handling."""

    def test_source_registry_lists_known_provider_names(self) -> None:
        """Validation should use the explicit source registry lookup."""
        from news.sources.registry import source_names

        self.assertIn("gdelt", source_names())
        self.assertIn("guardian", source_names())

    def test_empty_source_list_stays_explicit(self) -> None:
        """Delimiter-only source input should not broaden the search."""
        request = build_search_request(
            query="inflation",
            start_date="2026-02-01",
            end_date="2026-02-10",
            source_names=split_csv_values(","),
            language="",
            deduplicate=True,
        )

        self.assertEqual(request.source_names, ())
        self.assertIsNotNone(request.source_names)

    def test_rejects_invalid_newsapi_search_scope(self) -> None:
        """Unknown NewsAPI field scopes should fail instead of broadening search."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2026-02-01",
                end_date="2026-02-10",
                source_names=None,
                language="",
                deduplicate=True,
                newsapi_search_in="banana",
            )

        self.assertIn("newsapi_search_in", context.exception.message)

    def test_rejects_reverse_date_range(self) -> None:
        """Start dates after end dates should raise a 422 error."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query=" inflation ",
                start_date="2026-02-10",
                end_date="2026-02-01",
                source_names=None,
                language="EN",
                deduplicate=True,
            )

        self.assertIn("Start date", context.exception.message)

    def test_rejects_unknown_source(self) -> None:
        """Unregistered source names should fail fast."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2026-02-01",
                end_date="2026-02-10",
                source_names=["gdelt", "unknown-source"],
                language="",
                deduplicate=True,
            )

        self.assertIn("unknown-source", context.exception.message)

    def test_rejects_invalid_match_mode(self) -> None:
        """Unsupported advanced search options should fail validation."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2026-02-01",
                end_date="2026-02-10",
                source_names=None,
                language="",
                deduplicate=True,
                match_mode="impossible",
            )

        self.assertIn("match_mode", context.exception.message)

    def test_rejects_invalid_date_format(self) -> None:
        """Dates must use strict ISO calendar form."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2026-2-01",
                end_date="2026-02-10",
                source_names=None,
                language="",
                deduplicate=True,
            )

        self.assertIn("start", context.exception.message)

    def test_rejects_overlong_date_range(self) -> None:
        """Large backfills should be split into smaller windows."""
        with self.assertRaises(SearchValidationError) as context:
            build_search_request(
                query="inflation",
                start_date="2025-01-01",
                end_date="2026-02-10",
                source_names=None,
                language="",
                deduplicate=True,
            )

        self.assertIn("366 days", context.exception.message)

    def test_parses_provider_aware_advanced_filters(self) -> None:
        """Comma-separated advanced fields should normalize into tuples."""
        request = build_search_request(
            query="rates",
            start_date="2026-02-01",
            end_date="2026-02-10",
            source_names=("guardian", "nyt", "newsapi"),
            language="en",
            deduplicate=True,
            domain_filter="reuters.com, wsj.com",
            exclude_domains="reddit.com\nyoutube.com",
            provider_sort="relevance",
            section="business, world",
            news_desk="Business Day, Washington",
            guardian_tag="business/economics",
            newsapi_search_in="description,title",
        )

        self.assertEqual(request.include_domains, ("reuters.com", "wsj.com"))
        self.assertEqual(request.exclude_domains, ("reddit.com", "youtube.com"))
        self.assertEqual(request.provider_sort, "relevance")
        self.assertEqual(request.section_filters, ("business", "world"))
        self.assertEqual(request.news_desk_filters, ("Business Day", "Washington"))
        self.assertEqual(request.guardian_tags, ("business/economics",))
        self.assertEqual(request.newsapi_search_in, "title,description")


class DeduplicationTests(unittest.TestCase):
    """Test duplicate collapsing and URL normalization."""

    def test_canonicalize_url_removes_tracking_parameters(self) -> None:
        """Tracking parameters should not change the canonical URL."""
        canonical = canonicalize_url(
            "https://www.example.com/story/?utm_source=test&id=7#fragment"
        )
        self.assertEqual(canonical, "//example.com/story?id=7")

    def test_deduplicate_articles_merges_duplicate_sources(self) -> None:
        """Articles sharing a canonical URL should collapse into one record."""
        articles = [
            Article(
                title="Fed signals slower cuts",
                url="https://www.example.com/story?utm_source=feed&id=7",
                date="2026-02-10",
                source="gdelt",
                domain="example.com",
                language="en",
            ),
            Article(
                title="Fed signals slower cuts",
                url="http://example.com/story?id=7",
                date="2026-02-10",
                source="mediacloud",
                domain="Example.com",
                language="en",
            ),
        ]

        deduplicated = deduplicate_articles(articles)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0].duplicate_count, 2)
        self.assertEqual(
            deduplicated[0].matched_sources,
            ("gdelt", "mediacloud"),
        )

    def test_deduplicate_articles_merges_same_title_across_domains(self) -> None:
        """Same-day syndicated titles should merge even without a shared URL."""
        syndicated_title = (
            "On Capitol Hill, Democrats press Lutnick on Epstein ties and "
            "rare earth conflicts"
        )
        articles = [
            Article(
                title=syndicated_title,
                url="https://fox56.com/news/politics/lutnick-epstein-ties",
                date="2026-03-06",
                source="gdelt",
                domain="fox56.com",
                language="english",
            ),
            Article(
                title=syndicated_title,
                url="https://kpic.com/news/nation-world/lutnick-epstein-ties",
                date="2026-03-06",
                source="gdelt",
                domain="kpic.com",
                language="english",
            ),
        ]

        deduplicated = deduplicate_articles(articles)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0].duplicate_count, 2)
        self.assertEqual(deduplicated[0].source, "gdelt")

    def test_deduplicate_articles_keeps_richest_context_fields(self) -> None:
        """Duplicate collapsing should keep the richest available text fields."""
        articles = [
            Article(
                title="Fed minutes signal patience",
                url="https://www.example.com/story?id=7",
                date="2026-03-05",
                source="gdelt",
                domain="example.com",
                language="en",
                summary="Short summary.",
            ),
            Article(
                title="Fed minutes signal patience as cuts stay on hold",
                url="http://example.com/story?id=7&utm_source=feed",
                date="2026-03-05",
                source="guardian",
                domain="example.com",
                language="english",
                summary="A longer summary that keeps the richer explanation.",
                content="Detailed body text that should survive duplicate collapse.",
                section="Business",
                author="Jane Doe",
            ),
        ]

        deduplicated = deduplicate_articles(articles)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(
            deduplicated[0].title,
            "Fed minutes signal patience as cuts stay on hold",
        )
        self.assertEqual(
            deduplicated[0].summary,
            "A longer summary that keeps the richer explanation.",
        )
        self.assertEqual(
            deduplicated[0].content,
            "Detailed body text that should survive duplicate collapse.",
        )
        self.assertEqual(deduplicated[0].section, "Business")
        self.assertEqual(deduplicated[0].author, "Jane Doe")


class FilterBehaviorTests(unittest.TestCase):
    """Check local filter behavior that can quietly distort research output."""

    def test_language_filter_does_not_match_french_when_requesting_english(
        self,
    ) -> None:
        """The English shortcut should not keep French-language rows."""
        articles = [
            Article(
                title="French story",
                url="https://example.com/fr",
                date="2026-01-01",
                source="test",
                language="french",
            ),
            Article(
                title="English story",
                url="https://example.com/en",
                date="2026-01-01",
                source="test",
                language="english",
            ),
            Article(
                title="ISO English story",
                url="https://example.com/iso",
                date="2026-01-01",
                source="test",
                language="en",
            ),
            Article(
                title="Unknown language story",
                url="https://example.com/unknown",
                date="2026-01-01",
                source="test",
                language="",
            ),
        ]

        filtered = filter_by_language(articles, "en")

        self.assertEqual(
            [article.title for article in filtered],
            ["English story", "ISO English story", "Unknown language story"],
        )

    def test_language_filter_normalizes_common_provider_labels(self) -> None:
        """Language filtering should accept common tags without substring leaks."""
        articles = [
            Article(
                title="Regional English story",
                url="https://example.com/en-us",
                date="2026-01-01",
                source="test",
                language="en-US",
            ),
            Article(
                title="Whitespace English story",
                url="https://example.com/english",
                date="2026-01-01",
                source="test",
                language=" English ",
            ),
            Article(
                title="French story",
                url="https://example.com/french",
                date="2026-01-01",
                source="test",
                language="french",
            ),
        ]

        filtered = filter_by_language(articles, "en")

        self.assertEqual(
            [article.title for article in filtered],
            ["Regional English story", "Whitespace English story"],
        )

    def test_language_filter_supports_spanish_name_alias(self) -> None:
        """Spanish requests should match provider labels that spell the language."""
        articles = [
            Article(
                title="Spanish story",
                url="https://example.com/spanish",
                date="2026-01-01",
                source="test",
                language="spanish",
            ),
            Article(
                title="English story",
                url="https://example.com/english",
                date="2026-01-01",
                source="test",
                language="english",
            ),
        ]

        filtered = filter_by_language(articles, "es")

        self.assertEqual([article.title for article in filtered], ["Spanish story"])

    def test_date_desc_sort_keeps_title_ascending_inside_same_date(self) -> None:
        """Date descending should not reverse alphabetical title ties."""
        articles = [
            Article(
                title="Zulu",
                url="https://example.com/z",
                date="2026-01-01",
                source="test",
            ),
            Article(
                title="Alpha",
                url="https://example.com/a",
                date="2026-01-01",
                source="test",
            ),
            Article(
                title="Beta",
                url="https://example.com/b",
                date="2026-01-02",
                source="test",
            ),
        ]

        sorted_articles = sort_articles(articles, "date_desc")

        self.assertEqual(
            [article.title for article in sorted_articles],
            ["Beta", "Alpha", "Zulu"],
        )


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


class MediaCloudSourceTests(unittest.IsolatedAsyncioTestCase):
    """Check MediaCloud-specific rate-limit behavior."""

    async def test_mediacloud_search_respects_local_cooldown(self) -> None:
        """A recent 429 should block immediate follow-up requests locally."""
        source = MediaCloudSource()
        throttled_response = httpx.Response(
            429,
            headers={"Retry-After": "7"},
            request=httpx.Request("GET", source._BASE_URL),
        )
        from news.sources.common import record_rate_limit_cooldown
        from news.sources.providers.mediacloud import (
            DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
        )

        record_rate_limit_cooldown(
            source._cooldown,
            throttled_response,
            default_seconds=DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
        )

        with patch.object(source, "_fetch_story_list", new=AsyncMock()) as mock_fetch:
            with self.assertRaises(RuntimeError) as context:
                await source.search(
                    SourceSearchOptions(
                        query="Trump",
                        start_date="2026-02-03",
                        end_date="2026-03-06",
                    )
                )

        mock_fetch.assert_not_called()
        self.assertIn("Try again in", str(context.exception))


class MediaCloudPaginationTokenStoreTests(unittest.TestCase):
    """Check bounded continuation-token behavior for MediaCloud pagination."""

    def test_token_store_expires_old_entries(self) -> None:
        """Expired pagination tokens should not be reused."""
        from news.sources.providers.mediacloud import PaginationTokenStore

        current_time = 100.0

        def fake_clock() -> float:
            """Return mutable test time."""
            return current_time

        store = PaginationTokenStore(ttl_seconds=10, max_keys=2, clock=fake_clock)
        key = ("query", "2026-01-01", "2026-01-02")

        store.set(key, 2, "abc")
        self.assertEqual(store.get(key, 2), "abc")

        current_time = 111.0
        self.assertEqual(store.get(key, 2), "")

    def test_token_store_evicts_oldest_query_key_at_capacity(self) -> None:
        """The token store should not grow without a key limit."""
        from news.sources.providers.mediacloud import PaginationTokenStore

        store = PaginationTokenStore(ttl_seconds=60, max_keys=2)
        first_key = ("first",)
        second_key = ("second",)
        third_key = ("third",)

        store.set(first_key, 2, "first-token")
        store.set(second_key, 2, "second-token")
        store.set(third_key, 2, "third-token")

        self.assertEqual(store.get(first_key, 2), "")
        self.assertEqual(store.get(second_key, 2), "second-token")
        self.assertEqual(store.get(third_key, 2), "third-token")


class NewYorkTimesSourceTests(unittest.IsolatedAsyncioTestCase):
    """Check NYT-specific rate-limit behavior."""

    async def test_nyt_search_respects_local_cooldown(self) -> None:
        """A recent 429 should block immediate follow-up requests locally."""
        source = NewYorkTimesSource()
        throttled_response = httpx.Response(
            429,
            headers={"Retry-After": "5"},
            request=httpx.Request("GET", source._BASE_URL),
        )
        from news.sources.common import record_rate_limit_cooldown
        from news.sources.providers.nyt import DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS

        record_rate_limit_cooldown(
            source._cooldown,
            throttled_response,
            default_seconds=DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
        )

        with self.assertRaises(RuntimeError) as context:
            await source.search(
                SourceSearchOptions(
                    query="Trump",
                    start_date="2026-02-03",
                    end_date="2026-03-06",
                )
            )

        self.assertIn("Try again in", str(context.exception))


class AdditionalSourceAdapterTests(unittest.TestCase):
    """Check normalization logic for the newly added source adapters."""

    def test_guardian_to_article_normalizes_expected_fields(self) -> None:
        """Guardian search results should map cleanly into the unified schema."""
        article = GuardianSource._to_article(
            {
                "webTitle": "UK markets brace for rate decision",
                "webUrl": "https://www.theguardian.com/business/2026/mar/05/rates",
                "webPublicationDate": "2026-03-05T14:22:11Z",
                "sectionName": "Business",
                "fields": {
                    "lang": "en",
                    "trailText": "<p>Markets are waiting for the vote.</p>",
                    "body": "<p>Paragraph one.</p><p>Paragraph two.</p>",
                    "byline": "Jane Doe",
                },
            }
        )

        self.assertEqual(article.title, "UK markets brace for rate decision")
        self.assertEqual(article.date, "2026-03-05")
        self.assertEqual(article.source, "guardian")
        self.assertEqual(article.domain, "theguardian.com")
        self.assertEqual(article.language, "en")
        self.assertEqual(article.summary, "Markets are waiting for the vote.")
        self.assertEqual(article.content, "Paragraph one. Paragraph two.")
        self.assertEqual(article.section, "Business")
        self.assertEqual(article.author, "Jane Doe")

    def test_nyt_to_article_normalizes_expected_fields(self) -> None:
        """NYT article search results should map cleanly into the unified schema."""
        article = NewYorkTimesSource._to_article(
            {
                "headline": {"main": "Fed weighs next move"},
                "web_url": "https://www.nytimes.com/2026/03/05/business/fed.html",
                "pub_date": "2026-03-05T09:30:00+0000",
                "language": "en",
                "abstract": "The Fed is considering the next step.",
                "snippet": "Officials remain cautious.",
                "section_name": "Business",
                "byline": {"original": "By Jane Doe"},
            }
        )

        self.assertEqual(article.title, "Fed weighs next move")
        self.assertEqual(article.date, "2026-03-05")
        self.assertEqual(article.source, "nyt")
        self.assertEqual(article.domain, "nytimes.com")
        self.assertEqual(article.language, "en")
        self.assertEqual(article.summary, "The Fed is considering the next step.")
        self.assertEqual(article.content, "Officials remain cautious.")
        self.assertEqual(article.section, "Business")
        self.assertEqual(article.author, "By Jane Doe")

    def test_newsapi_helpers_build_expected_request_and_article(self) -> None:
        """NewsAPI request params and normalization should follow the shared model."""
        params = build_newsapi_params(
            options=SourceSearchOptions(
                query="fed",
                start_date="2026-03-01",
                end_date="2026-03-05",
                page=2,
                language="en",
                provider_sort="popularity",
                include_domains=("reuters.com", "wsj.com"),
                exclude_domains=("reddit.com",),
                newsapi_search_in="title,description",
            ),
        )
        article = newsapi_to_article(
            {
                "title": "Fed minutes signal patience",
                "url": "https://www.reuters.com/world/us/fed-minutes-2026-03-05/",
                "publishedAt": "2026-03-05T18:30:00Z",
                "description": "Officials are not rushing.",
                "content": "Longer text here. [+123 chars]",
                "author": "John Smith",
                "source": {"name": "Reuters"},
            },
            requested_language="en",
        )

        self.assertEqual(params["sortBy"], "popularity")
        self.assertEqual(params["searchIn"], "title,description")
        self.assertEqual(params["domains"], "reuters.com,wsj.com")
        self.assertEqual(params["excludeDomains"], "reddit.com")
        self.assertEqual(params["page"], "2")
        self.assertEqual(article.title, "Fed minutes signal patience")
        self.assertEqual(article.date, "2026-03-05")
        self.assertEqual(article.domain, "reuters.com")
        self.assertEqual(article.language, "en")
        self.assertEqual(article.summary, "Officials are not rushing.")
        self.assertEqual(article.content, "Longer text here.")
        self.assertEqual(article.section, "Reuters")
        self.assertEqual(article.author, "John Smith")


if __name__ == "__main__":
    unittest.main()
