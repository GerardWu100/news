"""Tests for MediaCloud cooldown and continuation-token behavior."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import httpx

from news.sources.base import SourceSearchOptions
from news.sources.providers.mediacloud import (
    DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
    MediaCloudSource,
    PaginationTokenStore,
)


class MediaCloudCooldownTests(unittest.IsolatedAsyncioTestCase):
    """Check provider-specific rate-limit behavior."""

    async def test_mediacloud_search_respects_local_cooldown(self) -> None:
        """A recent HTTP 429 should block immediate follow-up requests."""
        source = MediaCloudSource()
        throttled_response = httpx.Response(
            429,
            headers={"Retry-After": "7"},
            request=httpx.Request("GET", source._BASE_URL),
        )
        source._cooldown.activate_from_response(
            throttled_response,
            default_seconds=DEFAULT_RATE_LIMIT_COOLDOWN_SECONDS,
        )

        with (
            patch.object(source, "_fetch_story_list", new=AsyncMock()) as mock_fetch,
            self.assertRaises(RuntimeError) as context,
        ):
            await source.search(
                SourceSearchOptions(
                    query="Trump",
                    start_date="2026-02-03",
                    end_date="2026-03-06",
                )
            )

        mock_fetch.assert_not_called()
        self.assertIn("Try again in", str(context.exception))


class MediaCloudArticleMappingTests(unittest.TestCase):
    """Check normalization of MediaCloud story fields into ``Article`` rows."""

    def test_publish_date_is_trimmed_to_iso_date(self) -> None:
        """A datetime ``publish_date`` should become a bare ``YYYY-MM-DD``."""
        article = MediaCloudSource._to_article(
            {
                "title": "Story",
                "url": "https://example.com/story",
                "publish_date": "2024-01-15 00:00:00",
                "media_name": "example.com",
                "language": "en",
            }
        )

        # The trimmed date keeps cross-provider sorting and the same-day
        # syndicated-title dedup key consistent with the other adapters.
        self.assertEqual(article.date, "2024-01-15")


class MediaCloudPaginationTokenStoreTests(unittest.TestCase):
    """Check bounded continuation-token behavior."""

    def test_token_store_expires_old_entries(self) -> None:
        """Expired pagination tokens should not be reused."""
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
        """The token store should not grow beyond its key limit."""
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


class MediaCloudPaginationTests(unittest.IsolatedAsyncioTestCase):
    """Check sequential continuation-token handoff between provider pages."""

    async def test_search_stores_and_reuses_continuation_token(self) -> None:
        """Page two should send the token returned with page one."""
        source = MediaCloudSource()
        token_store = PaginationTokenStore()
        fetch_story_list = AsyncMock(
            side_effect=[
                {"stories": [], "pagination_token": "page-two-token"},
                {"stories": [], "pagination_token": ""},
            ]
        )
        page_one_options = SourceSearchOptions(
            query="inflation",
            start_date="2026-01-01",
            end_date="2026-01-31",
        )
        page_two_options = SourceSearchOptions(
            query="inflation",
            start_date="2026-01-01",
            end_date="2026-01-31",
            page=2,
        )

        # Page one records the provider's continuation token under page two.
        with (
            patch(
                "news.sources.providers.mediacloud._PAGINATION_TOKENS",
                token_store,
            ),
            patch.object(source, "_fetch_story_list", fetch_story_list),
        ):
            first_page = await source.search(page_one_options)
            second_page = await source.search(page_two_options)

        # The second request consumes that exact token and clears has-more when
        # the provider returns no next token.
        second_request_params = fetch_story_list.call_args_list[1].args[1]
        self.assertTrue(first_page.has_more)
        self.assertFalse(second_page.has_more)
        self.assertEqual(
            second_request_params["pagination_token"],
            "page-two-token",
        )
