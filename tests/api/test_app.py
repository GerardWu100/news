"""FastAPI route smoke tests for the public application endpoints."""

from __future__ import annotations

import unittest
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from news.api.app import create_app
from news.sources import SourceQueryReport
from news.sources.base import Article, SourceSearchOptions
from news.web.config import load_settings
from news.web.paths import config_path, static_dir

from tests.fixtures.search_results import build_provider_response


class AppRouteTests(unittest.TestCase):
    """Verify that the public HTTP routes stay wired correctly."""

    def setUp(self) -> None:
        """Create an isolated app with deterministic provider dependencies."""

        async def fake_search_executor(
            _options: SourceSearchOptions,
            _source_names: Sequence[str] | None,
        ) -> tuple[list[Article], list[SourceQueryReport]]:
            """Return one offline provider page."""
            return build_provider_response()

        def fake_source_status() -> list[dict[str, object]]:
            """Return deterministic source metadata."""
            return [
                {
                    "name": "guardian",
                    "display_name": "The Guardian",
                    "description": "Offline fake provider",
                    "available": True,
                }
            ]

        application = create_app(
            load_settings(),
            search_executor=fake_search_executor,
            source_status_provider=fake_source_status,
        )
        self.client = TestClient(application)

    def test_index_serves_frontend_shell(self) -> None:
        """The root page should serve the browser client."""
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Point-in-Time News", response.text)
        self.assertIn("copy-link-btn", response.text)

    def test_config_and_source_endpoints_return_json(self) -> None:
        """Lightweight JSON endpoints should stay reachable."""
        config_response = self.client.get("/api/config")
        sources_response = self.client.get("/api/sources")

        self.assertEqual(config_response.status_code, 200)
        self.assertEqual(sources_response.status_code, 200)
        self.assertIn("default_sources", config_response.json())
        self.assertIsInstance(sources_response.json(), list)

    def test_search_route_returns_structured_response(self) -> None:
        """Search responses should include results and metadata."""
        response = self.client.get(
            "/api/search",
            params={
                "q": "fed",
                "start": "2026-03-01",
                "end": "2026-03-20",
                "sources": "guardian",
                "language": "en",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["results"][0]["title"], "Fed holds rates steady")
        self.assertEqual(payload["meta"]["returned"], 1)
        self.assertEqual(payload["meta"]["source_reports"][0]["name"], "guardian")

    def test_search_route_maps_validation_errors_to_422(self) -> None:
        """The HTTP boundary should convert search validation errors to 422."""
        response = self.client.get(
            "/api/search",
            params={
                "q": "fed",
                "start": "2026-03-20",
                "end": "2026-03-01",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("Start date", response.json()["detail"])

    def test_export_csv_returns_csv_content_type(self) -> None:
        """CSV export should return a download-friendly text/csv response."""
        response = self.client.get(
            "/api/export/csv",
            params={"q": "fed", "start": "2026-03-01", "end": "2026-03-20"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertIn("Content-Disposition", response.headers)
        self.assertIn("Fed holds rates steady", response.text)

    def test_export_json_returns_json_array(self) -> None:
        """JSON export should return the raw article array."""
        response = self.client.get(
            "/api/export/json",
            params={"q": "fed", "start": "2026-03-01", "end": "2026-03-20"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Content-Disposition", response.headers)
        payload = response.json()
        self.assertIsInstance(payload, list)
        self.assertEqual(payload[0]["title"], "Fed holds rates steady")


class RuntimePathTests(unittest.TestCase):
    """Verify installed resources and operator-owned paths resolve correctly."""

    def test_static_path_finds_packaged_frontend(self) -> None:
        """Static assets should live under the importable package."""
        self.assertTrue((static_dir() / "index.html").exists())

    def test_config_path_prefers_explicit_path(self) -> None:
        """An explicit config path should override environment and CWD lookup."""
        with TemporaryDirectory() as temporary_directory:
            explicit_path = Path(temporary_directory) / "custom.toml"
            explicit_path.write_text("", encoding="utf-8")

            with patch.dict("os.environ", {"NEWS_CONFIG": "/ignored.toml"}):
                self.assertEqual(config_path(explicit_path), explicit_path.resolve())
