"""FastAPI route tests for the Google Trends endpoints."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from news.api.app import create_app
from news.trends.models import TrendsFetchError, TrendsValidationError
from news.web.config import load_settings
from tests.fixtures.trends_results import FIXED_FETCHED_AT, FakeTrendsClient


class FailingTrendsClient(FakeTrendsClient):
    """Fake raising the package error types to exercise status mapping."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def interest_over_time(self, keywords, *, timeframe, geo):  # type: ignore[override]
        raise self.error


class TrendsRouteTests(unittest.TestCase):
    """Verify the trends routes serialize results and map errors."""

    def setUp(self) -> None:
        """Create an isolated app with the offline trends fake."""
        application = create_app(load_settings(), trends_client=FakeTrendsClient())
        self.client = TestClient(application)

    def test_interest_route_returns_aligned_series(self) -> None:
        """The series response should carry dates, values, and fetch time."""
        response = self.client.get(
            "/api/trends/interest",
            params={"q": "bitcoin,ethereum", "timeframe": "today 3-m", "geo": "US"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["keywords"], ["bitcoin", "ethereum"])
        self.assertEqual(payload["dates"], ["2026-08-01", "2026-08-02"])
        self.assertEqual(payload["values"]["bitcoin"], [40, 60])
        self.assertEqual(payload["is_partial"], [False, True])
        self.assertEqual(payload["fetched_at"], FIXED_FETCHED_AT)

    def test_regions_route_returns_breakdown(self) -> None:
        """The regional response should carry one row per region."""
        response = self.client.get(
            "/api/trends/regions",
            params={"q": "bitcoin", "resolution": "REGION"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["resolution"], "REGION")
        self.assertEqual(payload["regions"][0]["region"], "New York")
        self.assertEqual(payload["regions"][0]["values"], {"bitcoin": 100})

    def test_related_route_returns_top_and_rising(self) -> None:
        """The related response should carry both query lists."""
        response = self.client.get("/api/trends/related", params={"q": "bitcoin"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["top"][0]["query"], "bitcoin price")
        self.assertEqual(payload["rising"][0]["value"], 250)

    def test_validation_error_maps_to_422(self) -> None:
        """Invalid inputs should surface as an unprocessable request."""
        application = create_app(
            load_settings(),
            trends_client=FailingTrendsClient(TrendsValidationError("bad input")),
        )

        response = TestClient(application).get(
            "/api/trends/interest", params={"q": "x"}
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "bad input")

    def test_fetch_error_maps_to_502(self) -> None:
        """Upstream Google failures should surface as a bad gateway."""
        application = create_app(
            load_settings(),
            trends_client=FailingTrendsClient(TrendsFetchError("rate limit")),
        )

        response = TestClient(application).get(
            "/api/trends/interest", params={"q": "x"}
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "rate limit")


if __name__ == "__main__":
    unittest.main()
