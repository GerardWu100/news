"""Static checks for frontend security-sensitive rendering helpers."""

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
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


if __name__ == "__main__":
    unittest.main()
