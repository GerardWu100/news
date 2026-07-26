"""Search orchestration and API payload assembly.

This module coordinates source fan-out, post-filtering, optional deduplication,
sorting, metadata construction, and optional request-level caching.
"""

from __future__ import annotations

from typing import Awaitable, Callable, Sequence

from ..sources import SourceQueryReport, search_all_detailed
from ..sources.base import Article, SourceSearchOptions
from .cache import SearchResultCache, build_default_search_cache
from .deduplication import deduplicate_articles
from .filters import apply_post_filters, sort_articles
from .models import SearchRequest, SearchResult

SearchExecutor = Callable[
    [SourceSearchOptions, Sequence[str] | None],
    Awaitable[tuple[list[Article], list[SourceQueryReport]]],
]
DEFAULT_SEARCH_CACHE = build_default_search_cache()


async def run_search(
    request: SearchRequest,
    executor: SearchExecutor = search_all_detailed,
    *,
    use_cache: bool = True,
    cache: SearchResultCache | None = None,
) -> SearchResult:
    """Run one validated search request and return the API payload.

    Parameters
    ----------
    request : SearchRequest
        Fully validated, immutable request inputs for one search call.
    executor : SearchExecutor, optional
        Async source fan-out callable that returns normalized articles and
        per-source execution reports.
    use_cache : bool, optional
        When ``True``, read from and write to the provided cache.
    cache : SearchResultCache | None, optional
        In-memory cache instance. ``None`` uses the process-default cache.

    Returns
    -------
    SearchResult
        Normalized article rows and response metadata ready for API/CLI output.
    """
    active_cache = DEFAULT_SEARCH_CACHE if cache is None else cache

    # Return the cached payload early so repeated requests avoid provider calls.
    if use_cache:
        cached_result = active_cache.get(request)
        if cached_result is not None:
            return cached_result

    source_options = SourceSearchOptions(
        query=request.query,
        start_date=request.start_date,
        end_date=request.end_date,
        page=request.page,
        language=request.language,
        provider_sort=request.provider_sort,
        include_domains=request.include_domains,
        exclude_domains=request.exclude_domains,
        section_filters=request.section_filters,
        news_desk_filters=request.news_desk_filters,
        guardian_tags=request.guardian_tags,
        newsapi_search_in=request.newsapi_search_in,
    )
    raw_articles, source_reports = await executor(
        source_options,
        request.source_names,
    )

    # Apply local post-filters first, then optional deduplication, then sorting.
    # This order keeps behavior stable and makes each stage easy to inspect.
    filtered_articles = apply_post_filters(raw_articles, request)
    total_before_deduplication = len(filtered_articles)

    if request.deduplicate:
        processed_articles = deduplicate_articles(filtered_articles)
    else:
        processed_articles = list(filtered_articles)

    sorted_articles = sort_articles(processed_articles, request.sort_order)
    duplicates_removed = total_before_deduplication - len(sorted_articles)

    if request.source_names is not None:
        requested_sources = list(request.source_names)
    else:
        # When callers do not pin sources, report only currently available ones
        # so metadata reflects the fan-out set users actually queried.
        requested_sources = [
            report.name for report in source_reports if report.available
        ]

    result = SearchResult(
        articles=[article.to_dict() for article in sorted_articles],
        meta=_build_result_meta(
            request=request,
            source_reports=source_reports,
            requested_sources=requested_sources,
            total_before_deduplication=total_before_deduplication,
            duplicates_removed=duplicates_removed,
            returned_count=len(sorted_articles),
        ),
    )

    if use_cache:
        # Store the fully assembled result so future identical requests can skip
        # source fan-out and downstream filtering work.
        active_cache.set(request, result)

    return result


def _build_result_meta(
    *,
    request: SearchRequest,
    source_reports: Sequence[SourceQueryReport],
    requested_sources: list[str],
    total_before_deduplication: int,
    duplicates_removed: int,
    returned_count: int,
) -> dict[str, object]:
    """Build the metadata object returned in the API search response.

    Parameters
    ----------
    request : SearchRequest
        Validated request used for this search run.
    source_reports : Sequence[SourceQueryReport]
        Per-source fan-out execution reports.
    requested_sources : list[str]
        Resolved source names displayed in API metadata.
    total_before_deduplication : int
        Article count after local filtering and before deduplication.
    duplicates_removed : int
        Number of rows removed by deduplication.
    returned_count : int
        Final number of rows returned to the caller.

    Returns
    -------
    dict[str, object]
        JSON-serializable metadata dictionary for the response payload.
    """
    source_report_rows = [report.to_dict() for report in source_reports]
    # A single source with an available next page means the merged result can
    # still paginate forward, so we OR across all source reports.
    has_more_pages = any(report.has_more for report in source_reports)
    has_previous_page = request.page > 1

    return {
        "query": request.query,
        "start": request.start_date,
        "end": request.end_date,
        "language": request.language,
        "deduplicate": request.deduplicate,
        "exact_phrase": request.exact_phrase,
        "exclude_terms": list(request.exclude_terms),
        "include_domains": list(request.include_domains),
        "exclude_domains": list(request.exclude_domains),
        "search_scope": request.search_scope,
        "match_mode": request.match_mode,
        "provider_sort": request.provider_sort,
        "section_filters": list(request.section_filters),
        "news_desk_filters": list(request.news_desk_filters),
        "guardian_tags": list(request.guardian_tags),
        "newsapi_search_in": request.newsapi_search_in,
        "sort_order": request.sort_order,
        "page": request.page,
        "has_more": has_more_pages,
        "has_previous": has_previous_page,
        "returned": returned_count,
        "requested_sources": requested_sources,
        "total": returned_count,
        "total_before_deduplication": total_before_deduplication,
        "duplicates_removed": duplicates_removed,
        "source_reports": source_report_rows,
    }
