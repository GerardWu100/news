"""MediaCloud requires a collection on every search.

The story-list endpoint answers HTTP 422 when a request names neither a
collection ("cs") nor an individual outlet ("ss"), so the configured
collections must reach the request rather than being assumed.
"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from news.sources.base import SourceSearchOptions
from news.sources.providers.mediacloud import MediaCloudSource
from news.sources.settings import SourceSettings, configure_sources

SEARCH_OPTIONS = SourceSearchOptions(
    query="inflation",
    start_date="2025-01-01",
    end_date="2025-01-31",
)


def _settings(collections: tuple[int, ...]) -> SourceSettings:
    """Build source settings that differ only in the searched collections."""
    return SourceSettings(
        connect_timeout_seconds=25.0,
        read_timeout_seconds=20.0,
        mediacloud_collections=collections,
    )


class MediaCloudCollectionTests(unittest.IsolatedAsyncioTestCase):
    """Verify the configured collections are sent and required."""

    def setUp(self) -> None:
        """Record the settings in force so each test can restore them."""
        from news.sources.settings import current_source_settings

        self._original_settings = current_source_settings()
        self.addCleanup(configure_sources, self._original_settings)

    async def test_every_configured_collection_is_sent(self) -> None:
        """Two collections must arrive as two values, not one joined string.

        httpx turns a list value into a repeated query parameter, which is the
        form the provider expects, so the list must survive to the request.
        """
        configure_sources(_settings((34412234, 34412476)))
        source = MediaCloudSource()
        fetch = AsyncMock(return_value={"stories": [], "pagination_token": ""})

        with (
            patch.dict("os.environ", {"MEDIACLOUD_API_KEY": "test-key"}),
            patch.object(source, "_fetch_story_list", new=fetch),
        ):
            await source.search(SEARCH_OPTIONS)

        sent_params = fetch.await_args.args[1]
        self.assertEqual(sent_params["cs"], ["34412234", "34412476"])

    async def test_no_configured_collection_fails_before_the_request(self) -> None:
        """An empty list can only produce HTTP 422, so say so without asking."""
        configure_sources(_settings(()))

        with patch.dict("os.environ", {"MEDIACLOUD_API_KEY": "test-key"}):
            with self.assertRaises(RuntimeError) as raised:
                await MediaCloudSource().search(SEARCH_OPTIONS)

        self.assertIn("mediacloud_collections", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
