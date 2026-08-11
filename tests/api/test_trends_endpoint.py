"""Route tests for ``GET /api/trends/interest`` using an offline client."""

from __future__ import annotations

import unittest
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from news.api.app import create_app
from news.sources import SourceQueryReport
from news.sources.base import Article, SourceSearchOptions
from news.trends.models import TrendsFetchError
from news.web.config import load_settings
from tests.fixtures.authentication import (
    attach_session_cookie,
    build_login_sessions,
)
from tests.fixtures.trends_results import (
    LONG_WINDOW_SERIES,
    FailingTrendsClient,
    FakeTrendsClient,
)


async def _unused_search_executor(
    _options: SourceSearchOptions,
    _source_names: Sequence[str] | None,
) -> tuple[list[Article], list[SourceQueryReport]]:
    """Satisfy the application factory; the trends route never calls it."""
    return [], []


class TrendsEndpointTests(unittest.TestCase):
    """The route reuses the search query and window, and maps errors by fault."""

    def _build_client(self, trends_client: object) -> TestClient:
        """Create a signed-in test client wired to a given trends source."""
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        login_sessions = build_login_sessions(Path(temporary_directory.name))

        application = create_app(
            load_settings(),
            search_executor=_unused_search_executor,
            source_status_provider=list,
            login_sessions=login_sessions,
            trends_client=trends_client,
        )
        client = TestClient(application)
        attach_session_cookie(client, login_sessions)
        return client

    def test_route_returns_the_series(self) -> None:
        """A valid request returns dates, values, and the scale details."""
        client = self._build_client(FakeTrendsClient())

        response = client.get(
            "/api/trends/interest",
            params={"q": "bitcoin", "start": "2015-01-01", "end": "2015-01-04"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["keywords"], ["bitcoin", "ethereum"])
        self.assertEqual(payload["values"]["bitcoin"], [27.0, 28.0, 31.0, 41.0])
        self.assertEqual(payload["granularity"], "daily")
        self.assertEqual(payload["anchor_date"], "2015-01-04")

    def test_search_query_becomes_trends_keywords(self) -> None:
        """The same boolean query used for articles is reduced to keywords."""
        trends_client = FakeTrendsClient()
        client = self._build_client(trends_client)

        client.get(
            "/api/trends/interest",
            params={
                "q": '"central bank" AND inflation -crypto',
                "start": "2015-01-01",
                "end": "2015-01-04",
            },
        )

        self.assertEqual(
            trends_client.calls[0]["keywords"],
            ["central bank", "inflation"],
        )

    def test_window_is_passed_through_unchanged(self) -> None:
        """The trends window is the search window, not a shorthand."""
        trends_client = FakeTrendsClient()
        client = self._build_client(trends_client)

        client.get(
            "/api/trends/interest",
            params={"q": "bitcoin", "start": "2015-01-01", "end": "2015-01-04"},
        )

        self.assertEqual(trends_client.calls[0]["start_date"], "2015-01-01")
        self.assertEqual(trends_client.calls[0]["end_date"], "2015-01-04")

    def test_as_of_rebases_the_series(self) -> None:
        """A decision date drops later points and re-anchors the scale."""
        client = self._build_client(FakeTrendsClient(LONG_WINDOW_SERIES))

        response = client.get(
            "/api/trends/interest",
            params={
                "q": "bitcoin",
                "start": "2017-01-01",
                "end": "2017-09-15",
                "as_of": "2017-01-03",
            },
        )

        payload = response.json()
        self.assertEqual(payload["anchor_date"], "2017-01-03")
        self.assertEqual(len(payload["dates"]), 3)
        self.assertEqual(max(payload["values"]["bitcoin"]), 100.0)

    def test_unusable_query_returns_422(self) -> None:
        """A query with no searchable term is the caller's mistake."""
        client = self._build_client(FakeTrendsClient())

        response = client.get(
            "/api/trends/interest",
            params={"q": "AND OR", "start": "2015-01-01", "end": "2015-01-04"},
        )

        self.assertEqual(response.status_code, 422)

    def test_as_of_outside_the_window_returns_422(self) -> None:
        """A decision date the series cannot cover is rejected."""
        client = self._build_client(FakeTrendsClient())

        response = client.get(
            "/api/trends/interest",
            params={
                "q": "bitcoin",
                "start": "2015-01-01",
                "end": "2015-01-04",
                "as_of": "2020-01-01",
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_upstream_failure_returns_502(self) -> None:
        """A Google outage or rate limit is not the caller's fault."""
        client = self._build_client(
            FailingTrendsClient(TrendsFetchError("Google Trends rate limit reached"))
        )

        response = client.get(
            "/api/trends/interest",
            params={"q": "bitcoin", "start": "2015-01-01", "end": "2015-01-04"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertIn("rate limit", response.json()["detail"])

    def test_route_requires_a_signed_in_account(self) -> None:
        """Trends data is behind the same sign-in as article data."""
        temporary_directory = TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        application = create_app(
            load_settings(),
            search_executor=_unused_search_executor,
            source_status_provider=list,
            login_sessions=build_login_sessions(Path(temporary_directory.name)),
            trends_client=FakeTrendsClient(),
        )

        response = TestClient(application).get(
            "/api/trends/interest",
            params={"q": "bitcoin", "start": "2015-01-01", "end": "2015-01-04"},
        )

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
