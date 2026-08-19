"""Coordinate searches and assemble the API response.

This module coordinates parallel source requests, local filtering, optional
duplicate removal, sorting, search details, and optional request caching.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Awaitable, Callable, Sequence

from ..sources import SourceQueryReport, search_all_detailed
from ..sources.base import Article, SourceSearchOptions
from .cache import SearchResultCache
from .deduplication import deduplicate_articles
from .filters import apply_post_filters, sort_articles
from .models import SearchRequest, SearchResult

SearchExecutor = Callable[
    [SourceSearchOptions, Sequence[str] | None],
    Awaitable[tuple[list[Article], list[SourceQueryReport]]],
]

# Searches that are already running, keyed by the request that started them.
# Sources are rate limited, so two callers asking the same question at the same
# moment should cost one round of provider requests, not two. Entries are
# removed as soon as the search finishes.
InFlightSearchKey = tuple[SearchRequest, int, int]
_searches_in_flight: dict[InFlightSearchKey, asyncio.Task[SearchResult]] = {}


async def run_search(
    request: SearchRequest,
    executor: SearchExecutor = search_all_detailed,
    *,
    use_cache: bool = True,
    cache: SearchResultCache | None = None,
) -> SearchResult:
    """Run one validated search request and return the API response.

    An identical request that is already running is joined rather than
    repeated, so a reloaded browser page or two commands started together do
    not each spend the provider rate limits.

    Parameters
    ----------
    request : SearchRequest
        Fully validated request inputs for one search call.
    executor : SearchExecutor, optional
        Async function that queries sources and returns normalized articles and
        one report per source.
    use_cache : bool, optional
        When ``True``, read from and write to the provided cache.
    cache : SearchResultCache | None, optional
        Short-lived in-memory cache. ``None`` disables cache reads and writes.

    Returns
    -------
    SearchResult
        Normalized articles and search details ready for API or CLI output.
    """
    # Return cached data early so repeated requests avoid source calls.
    if use_cache and cache is not None:
        cached_result = cache.get(request)
        if cached_result is not None:
            return cached_result

    # Execution dependencies are part of the key. Two application instances
    # may ask the same question while using different source executors or
    # caches, and their results must never cross that boundary.
    search_key = (request, id(executor), id(cache))
    running_search = _searches_in_flight.get(search_key)
    if running_search is None:
        running_search = asyncio.ensure_future(
            _execute_search(request, executor, use_cache=use_cache, cache=cache)
        )
        _searches_in_flight[search_key] = running_search
        running_search.add_done_callback(
            lambda completed: _remove_completed_search(search_key, completed)
        )

    # Shield every caller, including the one that created the task. Otherwise
    # closing the first browser request cancels the provider work for everyone
    # who joined it.
    result = await asyncio.shield(running_search)

    # Every caller gets its own copy, so one caller editing the response cannot
    # change what another caller sees.
    return copy.deepcopy(result)


def _remove_completed_search(
    search_key: InFlightSearchKey,
    completed_search: asyncio.Task[SearchResult],
) -> None:
    """Remove one finished shared search without deleting a replacement task.

    Parameters
    ----------
    search_key : InFlightSearchKey
        Request and application-specific execution dependencies.
    completed_search : asyncio.Task[SearchResult]
        Provider task that reached a terminal state.
    """
    if _searches_in_flight.get(search_key) is completed_search:
        _searches_in_flight.pop(search_key, None)

    # Read the exception so a creator that disconnected without any remaining
    # waiter does not leave an unhandled-task warning in the server log.
    if not completed_search.cancelled():
        completed_search.exception()


async def _execute_search(
    request: SearchRequest,
    executor: SearchExecutor,
    *,
    use_cache: bool,
    cache: SearchResultCache | None,
) -> SearchResult:
    """Query the sources and assemble one response.

    Parameters
    ----------
    request : SearchRequest
        Fully validated request inputs for one search call.
    executor : SearchExecutor
        Async function that queries sources.
    use_cache : bool
        Whether the finished result should be stored.
    cache : SearchResultCache | None
        Cache to store the result in, when one was supplied.

    Returns
    -------
    SearchResult
        Normalized articles and search details.
    """
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
        processed_articles = filtered_articles

    sorted_articles = sort_articles(processed_articles, request.sort_order)
    duplicates_removed = total_before_deduplication - len(sorted_articles)

    if request.source_names is not None:
        requested_sources = list(request.source_names)
    else:
        # When callers do not pin sources, report only currently available ones
        # so the search details reflect the sources the user actually queried.
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

    if use_cache and cache is not None:
        # Store the fully assembled result so future identical requests can skip
        # source requests and later local filtering work.
        cache.set(request, result)

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
    """Build the search details returned with the API response.

    Parameters
    ----------
    request : SearchRequest
        Validated request used for this search run.
    source_reports : Sequence[SourceQueryReport]
        One report for each source request.
    requested_sources : list[str]
        Source names displayed in the API response.
    total_before_deduplication : int
        Article count after local filtering and before deduplication.
    duplicates_removed : int
        Number of rows removed by deduplication.
    returned_count : int
        Final number of rows returned to the caller.

    Returns
    -------
    dict[str, object]
        JSON-ready dictionary for the response.
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
