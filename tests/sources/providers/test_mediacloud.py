"""Tests for MediaCloud cooldown and continuation-token behavior."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import httpx

from news.sources.base import SourceSearchOptions
from news.sources.common import record_rate_limit_cooldown
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


if __name__ == "__main__":
    unittest.main()
