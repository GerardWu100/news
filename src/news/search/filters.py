"""Local filtering and sorting helpers for normalized provider results.

These filters run after source fan-out, so they apply consistently across all
providers even when upstream query semantics differ.
"""

from __future__ import annotations

import re
from typing import Sequence

from ..sources.base import Article
from .models import SearchRequest

BOOLEAN_KEYWORDS = {"and", "or", "not"}
LANGUAGE_ALIASES = {
    "en": {"en", "eng", "english"},
    "fr": {"fr", "fra", "fre", "french"},
    "es": {"es", "spa", "spanish"},
}
SEARCHABLE_FIELDS = (
    "title",
    "summary",
    "content",
    "section",
    "author",
    "domain",
    "url",
)


def apply_post_filters(
    articles: Sequence[Article],
    request: SearchRequest,
) -> list[Article]:
    """Apply local filters after provider fan-out."""
    # Run filters in a fixed order so each stage narrows the candidate set
    # before the next stage does more expensive text checks.
    filtered = filter_by_language(articles, request.language)
    filtered = filter_by_include_domains(filtered, request.include_domains)
    filtered = filter_by_exclude_domains(filtered, request.exclude_domains)
    filtered = filter_by_query_terms(
        filtered,
        query=request.query,
        search_scope=request.search_scope,
        match_mode=request.match_mode,
    )
    filtered = filter_by_exact_phrase(
        filtered,
        exact_phrase=request.exact_phrase,
        search_scope=request.search_scope,
    )
    filtered = filter_by_exclude_terms(
        filtered,
        exclude_terms=request.exclude_terms,
        search_scope=request.search_scope,
    )
    return filtered


def filter_by_language(
    articles: Sequence[Article],
    language: str,
) -> list[Article]:
    """Apply a language filter without substring false positives."""
    requested_language = normalize_language_label(language)
    if not requested_language:
        return list(articles)

    accepted_labels = LANGUAGE_ALIASES.get(requested_language, {requested_language})
    filtered_articles: list[Article] = []
    for article in articles:
        article_language = normalize_language_label(article.language)
        if not article_language:
            filtered_articles.append(article)
            continue
        if article_language in accepted_labels:
            filtered_articles.append(article)

    return filtered_articles


def normalize_language_label(value: str) -> str:
    """Normalize provider language labels into comparable lowercase tokens."""
    cleaned_value = value.strip().lower()
    if not cleaned_value:
        return ""

    first_token = re.split(r"[^a-z]+", cleaned_value, maxsplit=1)[0]
    for canonical_label, aliases in LANGUAGE_ALIASES.items():
        if first_token in aliases:
            return canonical_label

    return first_token


def filter_by_include_domains(
    articles: Sequence[Article],
    include_domains: Sequence[str],
) -> list[Article]:
    """Keep articles whose domain matches one requested substring."""
    if not include_domains:
        return list(articles)

    filtered_articles: list[Article] = []
    for article in articles:
        # Normalize the domain once per article so the substring checks stay
        # cheap and easy to trace.
        article_domain = article.domain.lower()
        if any(include_domain in article_domain for include_domain in include_domains):
            filtered_articles.append(article)

    return filtered_articles


def filter_by_exclude_domains(
    articles: Sequence[Article],
    exclude_domains: Sequence[str],
) -> list[Article]:
    """Drop articles whose domain matches an excluded substring."""
    if not exclude_domains:
        return list(articles)

    filtered_articles: list[Article] = []
    for article in articles:
        # Reuse the lowercased domain so the exclusion check mirrors the include
        # path and stays easy to inspect in a debugger.
        article_domain = article.domain.lower()
        if all(
            excluded_domain not in article_domain for excluded_domain in exclude_domains
        ):
            filtered_articles.append(article)

    return filtered_articles


def filter_by_query_terms(
    articles: Sequence[Article],
    query: str,
    search_scope: str,
    match_mode: str,
) -> list[Article]:
    """Enforce keyword presence after provider search when requested.

    ``match_mode`` has already been validated at the request boundary, so this
    helper can keep the matching branches focused on the two local modes.
    """
    if match_mode == "provider":
        return list(articles)

    query_terms = extract_query_terms(query)
    if not query_terms:
        return list(articles)

    filtered_articles: list[Article] = []
    for article in articles:
        # Build one normalized text blob per article so term checks reuse the
        # same representation regardless of the selected match mode.
        searchable_text = build_searchable_text(article, search_scope)
        if match_mode == "all_terms":
            term_match = all(term in searchable_text for term in query_terms)
        else:
            # ``any_term`` is the only other local mode; invalid modes are
            # rejected before ``SearchRequest`` objects are built.
            term_match = any(term in searchable_text for term in query_terms)
        if term_match:
            filtered_articles.append(article)

    return filtered_articles


def filter_by_exact_phrase(
    articles: Sequence[Article],
    exact_phrase: str,
    search_scope: str,
) -> list[Article]:
    """Keep articles containing an exact normalized phrase."""
    normalized_phrase = normalize_for_match(exact_phrase)
    if not normalized_phrase:
        return list(articles)

    matching_articles: list[Article] = []
    for article in articles:
        # Phrase matching uses the same normalized text blob as term matching so
        # both filters see the same field scope.
        searchable_text = build_searchable_text(article, search_scope)
        if normalized_phrase in searchable_text:
            matching_articles.append(article)

    return matching_articles


def filter_by_exclude_terms(
    articles: Sequence[Article],
    exclude_terms: Sequence[str],
    search_scope: str,
) -> list[Article]:
    """Drop articles containing excluded terms in the selected scope."""
    normalized_exclusions: list[str] = []
    for term in exclude_terms:
        normalized_term = normalize_for_match(term)
        if normalized_term:
            normalized_exclusions.append(normalized_term)

    if not normalized_exclusions:
        return list(articles)

    kept_articles: list[Article] = []
    for article in articles:
        # Compute searchable text once per article instead of once per
        # exclusion term so this block is easier to reason about.
        searchable_text = build_searchable_text(article, search_scope)
        if all(exclusion not in searchable_text for exclusion in normalized_exclusions):
            kept_articles.append(article)
    return kept_articles


def sort_articles(articles: Sequence[Article], sort_order: str) -> list[Article]:
    """Sort articles by date and title for stable output."""
    # Python's sort is stable, so title order is preserved inside each date
    # bucket when the second pass sorts by date (including descending).
    sorted_by_title = sorted(articles, key=lambda article: article.title.lower())
    date_descending = sort_order != "date_asc"
    return sorted(
        sorted_by_title,
        key=lambda article: article.date,
        reverse=date_descending,
    )


def build_searchable_text(article: Article, search_scope: str) -> str:
    """Build a normalized text blob for post-filter matching."""
    if search_scope == "title":
        return normalize_for_match(article.title)

    # Keep provider-specific fields in one shared text blob so local matching
    # works consistently even when adapters expose different metadata richness.
    raw_fields = [getattr(article, field_name) for field_name in SEARCHABLE_FIELDS]
    return normalize_for_match(" ".join(raw_fields))


def extract_query_terms(query: str) -> tuple[str, ...]:
    """Extract query terms for simple local match enforcement."""
    terms = [
        token
        for token in re.findall(r"[A-Za-z0-9]+", query.lower())
        if len(token) > 1 and token not in BOOLEAN_KEYWORDS
    ]
    return tuple(dict.fromkeys(terms))


def normalize_for_match(value: str) -> str:
    """Normalize text for local search filters and deduplication keys."""
    return re.sub(r"\W+", " ", value.lower()).strip()
