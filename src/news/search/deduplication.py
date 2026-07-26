"""Deduplication helpers for merged multi-provider article results."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..sources.base import Article
from .filters import normalize_for_match

TRACKING_QUERY_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ocid",
    "ref",
    "spm",
    "utm_campaign",
    "utm_content",
    "utm_id",
    "utm_medium",
    "utm_name",
    "utm_reader",
    "utm_source",
    "utm_term",
    "xtor",
}

MIN_TITLE_LENGTH_FOR_SYNDICATION = 32
MIN_TITLE_TOKENS_FOR_SYNDICATION = 5
TEXT_MERGE_FIELDS = (
    "title",
    "domain",
    "language",
    "summary",
    "content",
    "section",
    "author",
)


def deduplicate_articles(articles: Sequence[Article]) -> list[Article]:
    """Collapse duplicate articles using URL and title passes."""
    url_groups: dict[str, list[Article]] = {}
    articles_without_url: list[Article] = []

    # First pass: group by canonical URL because exact-link duplicates are the
    # most reliable match across providers.
    for article in articles:
        canonical_url = canonicalize_url(article.url)
        if canonical_url:
            url_groups.setdefault(canonical_url, []).append(article)
            continue
        articles_without_url.append(article)

    # Second pass: merge URL groups, then run a weaker syndicated-title pass
    # for rows where URL matching is unavailable or inconsistent.
    merged_url_articles = [
        _merge_duplicate_group(group) for group in url_groups.values()
    ]
    return _deduplicate_by_syndicated_title(
        [*merged_url_articles, *articles_without_url]
    )


def canonicalize_url(raw_url: str) -> str:
    """Normalize a URL so equivalent links compare equal."""
    cleaned = raw_url.strip()
    if not cleaned:
        return ""

    parsed = urlsplit(cleaned)
    if not parsed.netloc:
        return ""

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    normalized_query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    normalized_query = urlencode(sorted(normalized_query_pairs))
    normalized_path = parsed.path.rstrip("/")

    return urlunsplit(("", host, normalized_path, normalized_query, ""))


def _deduplicate_by_syndicated_title(articles: Sequence[Article]) -> list[Article]:
    """Merge same-day syndicated headlines after URL variants are collapsed."""
    title_groups: dict[str, list[Article]] = {}
    passthrough_articles: list[Article] = []

    for article in articles:
        syndicated_title_key = syndicated_title_fingerprint(article)
        if not syndicated_title_key:
            # Keep low-confidence rows unchanged rather than forcing a weak
            # title-only merge.
            passthrough_articles.append(article)
            continue
        title_groups.setdefault(syndicated_title_key, []).append(article)

    merged_title_articles = [
        _merge_duplicate_group(group) for group in title_groups.values()
    ]
    return [*merged_title_articles, *passthrough_articles]


def syndicated_title_fingerprint(article: Article) -> str:
    """Build a domain-agnostic key for obvious same-day syndicated headlines."""
    normalized_title = normalize_for_match(article.title)
    if not is_syndication_candidate(normalized_title):
        return ""

    return f"{article.date}|{normalized_title}"


def is_syndication_candidate(normalized_title: str) -> bool:
    """Return ``True`` when a title is descriptive enough for title dedupe."""
    if len(normalized_title) < MIN_TITLE_LENGTH_FOR_SYNDICATION:
        return False

    title_tokens = normalized_title.split()
    return len(title_tokens) >= MIN_TITLE_TOKENS_FOR_SYNDICATION


def _merge_duplicate_group(group: Sequence[Article]) -> Article:
    """Keep the richest article representation and attach duplicate metadata."""
    # Use a quality score so we preserve the record with the most useful
    # context fields before overlaying the longest text snippets.
    best_article = max(group, key=_article_quality_key)
    matched_sources = tuple(sorted({article.source for article in group}))
    merged_text_fields = {
        field_name: _pick_richest_text(
            group,
            lambda article, field=field_name: getattr(article, field),
        )
        for field_name in TEXT_MERGE_FIELDS
    }
    return replace(
        best_article,
        **merged_text_fields,
        matched_sources=matched_sources,
        duplicate_count=len(group),
    )


def _pick_richest_text(
    group: Sequence[Article],
    value_getter: Callable[[Article], str],
) -> str:
    """Return the longest non-empty text value from one duplicate group."""
    best_value = ""
    for article in group:
        candidate_value = value_getter(article).strip()
        if len(candidate_value) > len(best_value):
            best_value = candidate_value
    return best_value


def _article_quality_key(article: Article) -> tuple[int, int, int, int, int, int]:
    """Score records so deduplication keeps the richest representation."""
    return (
        int(bool(article.url)),
        len(article.content.strip()),
        len(article.summary.strip()),
        int(bool(article.section)),
        int(bool(article.author)),
        len(article.title.strip()),
    )
