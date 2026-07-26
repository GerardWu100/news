"""Builders for complete search results shared by boundary and cache tests."""

from __future__ import annotations

from news.search.models import SearchResult
from news.sources import SourceQueryReport
from news.sources.base import Article


def build_search_result(
    title: str,
    *,
    query: str | None = None,
    include_source_report: bool = True,
) -> SearchResult:
    """Build one schema-complete result with deterministic metadata.

    Parameters
    ----------
    title : str
        Article title placed in the result row.
    query : str | None, optional
        Metadata query. ``None`` reuses the title.
    include_source_report : bool, optional
        Whether metadata includes a successful Guardian execution report.

    Returns
    -------
    SearchResult
        One-article result accepted by the API response and cache boundaries.
    """
    source_reports: list[dict[str, object]] = []
    if include_source_report:
        source_reports.append(
            {
                "name": "guardian",
                "display_name": "The Guardian",
                "available": True,
                "requested": True,
                "returned": 1,
                "has_more": False,
                "error": "",
            }
        )

    active_query = title if query is None else query
    return SearchResult(
        articles=[
            {
                "title": title,
                "url": "https://example.com/story",
                "date": "2026-03-20",
                "source": "guardian",
                "domain": "example.com",
                "language": "en",
                "summary": "Officials left the policy rate unchanged.",
                "content": "",
                "section": "Business",
                "author": "Jane Doe",
                "matched_sources": ["guardian"],
                "duplicate_count": 1,
            }
        ],
        meta={
            "query": active_query,
            "start": "2026-03-01",
            "end": "2026-03-20",
            "language": "en",
            "deduplicate": True,
            "exact_phrase": "",
            "exclude_terms": [],
            "include_domains": [],
            "exclude_domains": [],
            "search_scope": "all",
            "match_mode": "provider",
            "provider_sort": "default",
            "section_filters": [],
            "news_desk_filters": [],
            "guardian_tags": [],
            "newsapi_search_in": "all",
            "sort_order": "date_desc",
            "page": 1,
            "has_more": False,
            "has_previous": False,
            "returned": 1,
            "requested_sources": ["guardian"],
            "total": 1,
            "total_before_deduplication": 1,
            "duplicates_removed": 0,
            "source_reports": source_reports,
        },
    )


def build_provider_response(
    title: str = "Fed holds rates steady",
) -> tuple[list[Article], list[SourceQueryReport]]:
    """Build one normalized provider page and its execution report.

    Parameters
    ----------
    title : str, optional
        Title used by the normalized article.

    Returns
    -------
    tuple[list[Article], list[SourceQueryReport]]
        One article and its successful Guardian source report.
    """
    articles = [
        Article(
            title=title,
            url="https://example.com/story",
            date="2026-03-20",
            source="guardian",
            domain="example.com",
            language="en",
            summary="Officials left the policy rate unchanged.",
            section="Business",
            author="Jane Doe",
        )
    ]
    reports = [
        SourceQueryReport(
            name="guardian",
            display_name="The Guardian",
            available=True,
            requested=True,
            returned=1,
        )
    ]
    return articles, reports
