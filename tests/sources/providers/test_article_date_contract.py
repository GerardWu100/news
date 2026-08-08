"""Cross-provider contract test for the ``Article.date`` format.

Every adapter receives a different wire format from its upstream API, so the
conversion itself cannot be shared. What every adapter must agree on is the
output: ``Article.date`` is either a bare ``YYYY-MM-DD`` calendar date or an
empty string when upstream supplied nothing usable.

Two pieces of the pipeline read ``Article.date`` as an opaque string and break
quietly when an adapter drifts from that format:

- ``news.search.filters.sort_articles`` orders results by comparing the raw
  string, so "2024-01-15 00:00:00" sorts after every bare "2024-01-15" instead
  of alongside it.
- ``news.search.deduplication.syndicated_title_fingerprint`` builds its key as
  "{date}|{title}", so a differently formatted date can never match a same-day
  duplicate from another provider.

Neither failure raises. This test is the enforcement point that a new or
changed adapter has to pass.
"""

from __future__ import annotations

import re
import unittest

from news.sources.providers.acled import AcledSource
from news.sources.providers.gdelt import GdeltSource
from news.sources.providers.guardian import GuardianSource
from news.sources.providers.mediacloud import MediaCloudSource
from news.sources.providers.newsapi import _to_article as newsapi_to_article
from news.sources.providers.nyt import NewYorkTimesSource

ISO_CALENDAR_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")

EXPECTED_DATE = "2024-01-15"

# One row per adapter: (provider name, callable taking a raw upstream record,
# a raw record whose date field carries a time component in that provider's
# own wire format). The expected result is EXPECTED_DATE for every row.
PROVIDER_DATE_CASES = (
    (
        "acled",
        AcledSource._to_article,
        {"event_date": "2024-01-15", "notes": "Event text", "source_url": "https://a/1"},
    ),
    (
        "gdelt",
        GdeltSource._to_article,
        {"seendate": "20240115T120000Z", "title": "Story", "url": "https://a/2"},
    ),
    (
        "guardian",
        GuardianSource._to_article,
        {"webPublicationDate": "2024-01-15T12:00:00Z", "webTitle": "Story",
         "webUrl": "https://a/3"},
    ),
    (
        "mediacloud",
        MediaCloudSource._to_article,
        {"publish_date": "2024-01-15 00:00:00", "title": "Story",
         "url": "https://a/4"},
    ),
    (
        "newsapi",
        lambda raw: newsapi_to_article(raw, requested_language="en"),
        {"publishedAt": "2024-01-15T12:00:00Z", "title": "Story",
         "url": "https://a/5"},
    ),
    (
        "nyt",
        NewYorkTimesSource._to_article,
        {"pub_date": "2024-01-15T12:00:00+0000", "headline": {"main": "Story"},
         "web_url": "https://a/6"},
    ),
)


class ArticleDateContractTests(unittest.TestCase):
    """Every adapter must emit a bare ISO calendar date."""

    def test_every_provider_trims_its_date_to_iso_calendar_form(self) -> None:
        """A date carrying a time component becomes a bare YYYY-MM-DD."""
        for provider_name, to_article, raw_record in PROVIDER_DATE_CASES:
            with self.subTest(provider=provider_name):
                article = to_article(raw_record)
                self.assertEqual(article.date, EXPECTED_DATE)

    def test_every_provider_handles_a_missing_date(self) -> None:
        """An absent date field yields an empty string, never a partial one."""
        for provider_name, to_article, raw_record in PROVIDER_DATE_CASES:
            with self.subTest(provider=provider_name):
                record_without_date = {
                    key: value
                    for key, value in raw_record.items()
                    if not key.lower().endswith(("date", "publishedat"))
                }
                article = to_article(record_without_date)
                self.assertEqual(article.date, "")

    def test_date_matches_the_iso_calendar_pattern(self) -> None:
        """Guard the format itself, not only the one sample value."""
        for provider_name, to_article, raw_record in PROVIDER_DATE_CASES:
            with self.subTest(provider=provider_name):
                article = to_article(raw_record)
                self.assertRegex(article.date, ISO_CALENDAR_DATE_PATTERN)


if __name__ == "__main__":
    unittest.main()
