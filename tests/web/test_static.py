"""Static checks for frontend security-sensitive rendering helpers."""

from __future__ import annotations

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML_PATH = PROJECT_ROOT / "src" / "news" / "web" / "static" / "index.html"
APP_JS_PATH = PROJECT_ROOT / "src" / "news" / "web" / "static" / "scripts" / "app.js"
STYLES_CSS_PATH = PROJECT_ROOT / "src" / "news" / "web" / "static" / "styles.css"
RENDER_JS_PATH = (
    PROJECT_ROOT / "src" / "news" / "web" / "static" / "scripts" / "render.js"
)


class FrontendStaticSecurityTests(unittest.TestCase):
    """Check that provider-controlled URLs go through explicit sanitization."""

    def test_article_dialog_uses_safe_url_helper_for_links(self) -> None:
        """Article links should not render raw provider URLs into href."""
        render_source = RENDER_JS_PATH.read_text(encoding="utf-8")

        self.assertIn("function buildSafeArticleUrl", render_source)
        self.assertIn("const safeUrl = buildSafeArticleUrl(result.url)", render_source)
        self.assertNotIn('href="${result.url}"', render_source)


class FrontendResearchWorkflowTests(unittest.TestCase):
    """Check that the browser keeps point-in-time research controls visible."""

    def test_page_labels_end_date_as_information_boundary(self) -> None:
        """The form should explain the inclusive as-of boundary to users."""
        html = INDEX_HTML_PATH.read_text(encoding="utf-8")

        self.assertIn("Point-in-time research mode", html)
        self.assertIn("Through (as of)", html)
        self.assertIn('id="window-banner"', html)

    def test_page_presents_a_responsive_research_workflow(self) -> None:
        """The empty page should teach the workflow and respect motion settings."""
        html = INDEX_HTML_PATH.read_text(encoding="utf-8")
        styles = STYLES_CSS_PATH.read_text(encoding="utf-8")

        self.assertIn("Freeze the information set", html)
        self.assertIn('class="research-steps"', html)
        self.assertIn('class="results-heading"', html)
        self.assertIn('href="/static/favicon.svg"', html)
        self.assertIn('role="list" aria-label="Research features"', html)
        self.assertEqual(html.count('role="listitem"'), 3)
        self.assertIn("@media (prefers-reduced-motion: reduce)", styles)

    def test_completed_search_enables_exact_page_exports(self) -> None:
        """A completed search should bind JSON and CSV links to active filters."""
        app_source = APP_JS_PATH.read_text(encoding="utf-8")

        self.assertIn('buildExportUrl("json"', app_source)
        self.assertIn('buildExportUrl("csv"', app_source)
        self.assertIn("renderResearchWindow(payload.meta)", app_source)
