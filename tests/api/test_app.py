"""FastAPI route smoke tests for the public application endpoints."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from news.api.app import app
from tests.fixtures.search_results import build_search_result

FAKE_RESULT = build_search_result("Fed holds rates steady", query="fed")


class AppRouteTests(unittest.TestCase):
    """Verify that the public HTTP routes stay wired correctly."""

    def setUp(self) -> None:
        """Create a fresh test client per test."""
        self.client = TestClient(app)

    def test_index_serves_frontend_shell(self) -> None:
        """The root page should serve the browser client."""
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("News Explorer", response.text)
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
        with patch("news.api.app.run_search", new=AsyncMock(return_value=FAKE_RESULT)):
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
        with patch("news.api.app.run_search", new=AsyncMock(return_value=FAKE_RESULT)):
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
        with patch("news.api.app.run_search", new=AsyncMock(return_value=FAKE_RESULT)):
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
        from news.web.paths import static_dir

        self.assertTrue((static_dir() / "index.html").exists())

    def test_config_path_prefers_explicit_path(self) -> None:
        """An explicit config path should override environment and CWD lookup."""
        from news.web.paths import config_path

        with TemporaryDirectory() as temporary_directory:
            explicit_path = Path(temporary_directory) / "custom.toml"
            explicit_path.write_text("", encoding="utf-8")

            with patch.dict("os.environ", {"NEWS_CONFIG": "/ignored.toml"}):
                self.assertEqual(config_path(explicit_path), explicit_path.resolve())

    def test_missing_external_config_uses_packaged_defaults(self) -> None:
        """An installed app should start without a local config file."""
        from news.web.config import load_settings

        with TemporaryDirectory() as temporary_directory:
            with (
                patch("pathlib.Path.cwd", return_value=Path(temporary_directory)),
                patch.dict("os.environ", {}, clear=True),
            ):
                settings = load_settings()

        self.assertEqual(settings.cache.ttl_seconds, 300)
        self.assertEqual(settings.frontend.default_sources, ())


if __name__ == "__main__":
    unittest.main()
