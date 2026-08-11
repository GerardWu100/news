"""Static checks for browser security-sensitive display helpers."""

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
TRENDS_JS_PATH = (
    PROJECT_ROOT / "src" / "news" / "web" / "static" / "scripts" / "trends.js"
)


class FrontendStaticSecurityTests(unittest.TestCase):
    """Check that provider-controlled URLs go through explicit sanitization."""

    def test_article_dialog_uses_safe_url_helper_for_links(self) -> None:
        """Article links should not place raw source URLs in href."""
        render_source = RENDER_JS_PATH.read_text(encoding="utf-8")

        self.assertIn("function buildSafeArticleUrl", render_source)
        self.assertIn("const safeUrl = buildSafeArticleUrl(result.url)", render_source)
        self.assertNotIn('href="${result.url}"', render_source)


class FrontendResearchWorkflowTests(unittest.TestCase):
    """Check that the browser keeps the historical cutoff visible."""

    def test_page_labels_end_date_as_information_boundary(self) -> None:
        """The form should explain the inclusive as-of boundary to users."""
        html = INDEX_HTML_PATH.read_text(encoding="utf-8")

        self.assertIn("Historical research mode", html)
        self.assertIn("Through (cutoff)", html)
        self.assertIn('id="window-banner"', html)

    def test_page_presents_a_responsive_research_workflow(self) -> None:
        """The empty page should teach the workflow and respect motion settings."""
        html = INDEX_HTML_PATH.read_text(encoding="utf-8")
        styles = STYLES_CSS_PATH.read_text(encoding="utf-8")

        self.assertIn("Set the cutoff before you form a view", html)
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


class FrontendSearchAttentionTests(unittest.TestCase):
    """Check the search-attention section the browser draws beside articles."""

    def test_page_carries_the_attention_section_and_its_controls(self) -> None:
        """The section needs its own geography, decision date, and trigger."""
        html = INDEX_HTML_PATH.read_text(encoding="utf-8")

        self.assertIn('id="trends-chart"', html)
        self.assertIn('id="trends-geo"', html)
        self.assertIn('id="trends-as-of"', html)
        self.assertIn('id="trends-btn"', html)
        self.assertIn("/static/scripts/trends.js", html)

    def test_attention_reuses_the_search_query_and_window(self) -> None:
        """A second set of query and date fields could silently drift apart."""
        trends_source = TRENDS_JS_PATH.read_text(encoding="utf-8")

        self.assertIn("readSearchForm", trends_source)
        self.assertNotIn('getElementById("query")', trends_source)
        self.assertNotIn('getElementById("start-date")', trends_source)

    def test_chart_is_drawn_without_an_external_library(self) -> None:
        """The page's security policy allows scripts only from this server."""
        html = INDEX_HTML_PATH.read_text(encoding="utf-8")
        trends_source = TRENDS_JS_PATH.read_text(encoding="utf-8")

        self.assertNotIn("<script src=\"http", html)
        self.assertIn("createElementNS", trends_source)

    def test_relative_scale_is_explained_where_the_chart_is_read(self) -> None:
        """A reader who takes 100 for "very high" misreads every chart."""
        html = INDEX_HTML_PATH.read_text(encoding="utf-8")
        trends_source = TRENDS_JS_PATH.read_text(encoding="utf-8")

        self.assertIn("relative index from 0 to 100", html)
        self.assertIn("not a number of searches", trends_source)
