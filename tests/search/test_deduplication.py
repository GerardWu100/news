"""Tests for cleaned URLs and repeated-article removal."""

from __future__ import annotations

import unittest

from news.search import canonicalize_url, deduplicate_articles
from news.sources.base import Article


class DeduplicationTests(unittest.TestCase):
    """Test duplicate collapsing and URL normalization."""

    def test_canonicalize_url_removes_tracking_parameters(self) -> None:
        """Tracking parameters should not change the canonical URL."""
        canonical = canonicalize_url(
            "https://www.example.com/story/?utm_source=test&id=7#fragment"
        )
        self.assertEqual(canonical, "//example.com/story?id=7")

    def test_deduplicate_articles_merges_duplicate_sources(self) -> None:
        """Articles sharing a canonical URL should collapse into one record."""
        articles = [
            Article(
                title="Fed signals slower cuts",
                url="https://www.example.com/story?utm_source=feed&id=7",
                date="2026-02-10",
                source="gdelt",
                domain="example.com",
                language="en",
            ),
            Article(
                title="Fed signals slower cuts",
                url="http://example.com/story?id=7",
                date="2026-02-10",
                source="mediacloud",
                domain="Example.com",
                language="en",
            ),
        ]

        deduplicated = deduplicate_articles(articles)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0].duplicate_count, 2)
        self.assertEqual(
            deduplicated[0].matched_sources,
            ("gdelt", "mediacloud"),
        )

    def test_deduplicate_articles_merges_same_title_across_domains(self) -> None:
        """Same-day syndicated titles should merge even without a shared URL."""
        syndicated_title = (
            "On Capitol Hill, Democrats press Lutnick on Epstein ties and "
            "rare earth conflicts"
        )
        articles = [
            Article(
                title=syndicated_title,
                url="https://fox56.com/news/politics/lutnick-epstein-ties",
                date="2026-03-06",
                source="gdelt",
                domain="fox56.com",
                language="english",
            ),
            Article(
                title=syndicated_title,
                url="https://kpic.com/news/nation-world/lutnick-epstein-ties",
                date="2026-03-06",
                source="gdelt",
                domain="kpic.com",
                language="english",
            ),
        ]

        deduplicated = deduplicate_articles(articles)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(deduplicated[0].duplicate_count, 2)
        self.assertEqual(deduplicated[0].source, "gdelt")

    def test_deduplicate_articles_preserves_metadata_across_both_passes(self) -> None:
        """Source names from URL matching must survive a later title merge."""
        syndicated_title = (
            "Federal Reserve signals a pause in interest rate hikes this year"
        )
        articles = [
            # gdelt and nyt share a canonical URL, so they collapse in the URL
            # pass before the title pass folds in the guardian record below.
            Article(
                title=syndicated_title,
                url="https://a.com/story?id=1",
                date="2026-02-10",
                source="gdelt",
                domain="a.com",
                language="en",
            ),
            Article(
                title=syndicated_title,
                url="https://a.com/story?id=1&utm_source=x",
                date="2026-02-10",
                source="nyt",
                domain="a.com",
                language="en",
            ),
            Article(
                title=syndicated_title,
                url="https://b.com/other",
                date="2026-02-10",
                source="guardian",
                domain="b.com",
                language="en",
            ),
        ]

        deduplicated = deduplicate_articles(articles)

        self.assertEqual(len(deduplicated), 1)
        # The title pass must union the URL-pass ``matched_sources`` instead of
        # only reading each member's ``source``, so nyt is not dropped.
        self.assertEqual(
            deduplicated[0].matched_sources,
            ("gdelt", "guardian", "nyt"),
        )
        # And ``duplicate_count`` must sum every original record (3), not just
        # the two members of the final title group.
        self.assertEqual(deduplicated[0].duplicate_count, 3)

    def test_deduplicate_articles_keeps_richest_context_fields(self) -> None:
        """Duplicate collapsing should keep the richest available text fields."""
        articles = [
            Article(
                title="Fed minutes signal patience",
                url="https://www.example.com/story?id=7",
                date="2026-03-05",
                source="gdelt",
                domain="example.com",
                language="en",
                summary="Short summary.",
            ),
            Article(
                title="Fed minutes signal patience as cuts stay on hold",
                url="http://example.com/story?id=7&utm_source=feed",
                date="2026-03-05",
                source="guardian",
                domain="example.com",
                language="english",
                summary="A longer summary that keeps the richer explanation.",
                content="Detailed body text that should survive duplicate collapse.",
                section="Business",
                author="Jane Doe",
            ),
        ]

        deduplicated = deduplicate_articles(articles)

        self.assertEqual(len(deduplicated), 1)
        self.assertEqual(
            deduplicated[0].title,
            "Fed minutes signal patience as cuts stay on hold",
        )
        self.assertEqual(
            deduplicated[0].summary,
            "A longer summary that keeps the richer explanation.",
        )
        self.assertEqual(
            deduplicated[0].content,
            "Detailed body text that should survive duplicate collapse.",
        )
        self.assertEqual(deduplicated[0].section, "Business")
        self.assertEqual(deduplicated[0].author, "Jane Doe")
