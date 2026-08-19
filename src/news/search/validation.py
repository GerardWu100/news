"""Validate and clean incoming search parameters.

This module enforces API constraints, cleans free-form query options, and
returns immutable ``SearchRequest`` objects used by the search service.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from ..sources.registry import source_names as registered_source_names
from .errors import SearchValidationError
from .models import SearchRequest

MAX_DATE_RANGE_DAYS = 366
ALLOWED_MATCH_MODES = {"provider", "all_terms", "any_term"}
ALLOWED_SEARCH_SCOPES = {"all", "title"}
ALLOWED_SORT_ORDERS = {"date_desc", "date_asc"}
ALLOWED_PROVIDER_SORTS = {
    "default",
    "newest",
    "oldest",
    "relevance",
    "popularity",
}
NEWSAPI_SEARCH_IN_FIELD_ORDER = ("title", "description", "content")
ALLOWED_NEWSAPI_SEARCH_IN_FIELDS = set(NEWSAPI_SEARCH_IN_FIELD_ORDER)


def build_search_request(
    query: str,
    start_date: str,
    end_date: str,
    source_names: Sequence[str] | None,
    language: str,
    deduplicate: bool,
    exact_phrase: str = "",
    exclude_terms: str = "",
    domain_filter: str = "",
    exclude_domains: str = "",
    search_scope: str = "all",
    match_mode: str = "provider",
    provider_sort: str = "default",
    section: str = "",
    news_desk: str = "",
    guardian_tag: str = "",
    newsapi_search_in: str = "all",
    sort_order: str = "date_desc",
    page: int = 1,
) -> SearchRequest:
    """Validate raw search inputs and build a ``SearchRequest``.

    Parameters
    ----------
    query : str
        Raw user query string.
    start_date : str
        Inclusive start date in ``YYYY-MM-DD`` format.
    end_date : str
        Inclusive end date in ``YYYY-MM-DD`` format.
    source_names : Sequence[str] | None
        Optional source-name list supplied by the caller.
    language : str
        Optional language hint shared across provider/local filtering.
    deduplicate : bool
        Whether to collapse duplicates after local filtering.
    exact_phrase : str, optional
        Optional phrase that must be present in selected fields.
    exclude_terms : str, optional
        Comma/newline-delimited terms to remove from local results.
    domain_filter : str, optional
        Comma/newline-delimited include-domain filters.
    exclude_domains : str, optional
        Comma/newline-delimited exclude-domain filters.
    search_scope : str, optional
        Local matching scope (``all`` or ``title``).
    match_mode : str, optional
        Local keyword mode (``provider``, ``all_terms``, ``any_term``).
    provider_sort : str, optional
        Shared provider sort hint.
    section : str, optional
        Comma/newline-delimited section filters for supported providers.
    news_desk : str, optional
        Comma/newline-delimited New York Times desk filters.
    guardian_tag : str, optional
        Comma/newline-delimited Guardian tag filters.
    newsapi_search_in : str, optional
        NewsAPI field scope list.
    sort_order : str, optional
        Final merged sort order.
    page : int, optional
        1-based source page index.

    Returns
    -------
    SearchRequest
        Cleaned request object used by the search service.
    """
    # Clean the query first so an empty value fails before the other fields are
    # parsed.
    cleaned_query = query.strip()
    if not cleaned_query:
        raise SearchValidationError("Query cannot be empty")

    # Parse and validate the date window up front because every provider call
    # and cache key depends on this normalized range.
    parsed_start = _parse_iso_date(start_date, field_name="start")
    parsed_end = _parse_iso_date(end_date, field_name="end")
    if parsed_start > parsed_end:
        raise SearchValidationError("Start date must be on or before end date")
    # Both boundaries are included. The difference counts gaps between dates,
    # so add one before enforcing the documented calendar-day limit.
    date_range_days = (parsed_end - parsed_start).days + 1
    if date_range_days > MAX_DATE_RANGE_DAYS:
        raise SearchValidationError(
            "Date range cannot exceed 366 days. "
            "Split larger backfills into smaller windows."
        )

    # Clean choice-like parameters once so later code can treat them as valid.
    normalized_search_scope = _validate_choice(
        search_scope.strip().lower() or "all",
        allowed_values=ALLOWED_SEARCH_SCOPES,
        field_name="search_scope",
    )
    normalized_match_mode = _validate_choice(
        match_mode.strip().lower() or "provider",
        allowed_values=ALLOWED_MATCH_MODES,
        field_name="match_mode",
    )
    normalized_sort_order = _validate_choice(
        sort_order.strip().lower() or "date_desc",
        allowed_values=ALLOWED_SORT_ORDERS,
        field_name="sort_order",
    )
    normalized_provider_sort = _validate_choice(
        provider_sort.strip().lower() or "default",
        allowed_values=ALLOWED_PROVIDER_SORTS,
        field_name="provider_sort",
    )
    normalized_newsapi_search_in = _normalize_newsapi_search_in(newsapi_search_in)

    if page < 1:
        raise SearchValidationError("Page must be at least 1")

    # Build one immutable request object for cache keys and response details;
    # later code does not need to clean these values again.
    return SearchRequest(
        query=cleaned_query,
        start_date=parsed_start.isoformat(),
        end_date=parsed_end.isoformat(),
        source_names=_normalize_source_names(source_names),
        language=language.strip().lower(),
        deduplicate=deduplicate,
        exact_phrase=exact_phrase.strip(),
        exclude_terms=_parse_list_field(exclude_terms),
        include_domains=_parse_list_field(domain_filter),
        exclude_domains=_parse_list_field(exclude_domains),
        search_scope=normalized_search_scope,
        match_mode=normalized_match_mode,
        provider_sort=normalized_provider_sort,
        section_filters=_parse_list_field(section, lowercase=False),
        news_desk_filters=_parse_list_field(news_desk, lowercase=False),
        guardian_tags=_parse_list_field(guardian_tag, lowercase=False),
        newsapi_search_in=normalized_newsapi_search_in,
        sort_order=normalized_sort_order,
        page=page,
    )


def split_csv_values(raw_value: str) -> tuple[str, ...] | None:
    """Split one comma-delimited boundary field into ordered values.

    Blank input keeps the historical "use defaults" behavior. Delimiter-only
    input still returns an explicit empty tuple so boundary callers can
    distinguish "no source names were provided" from "use every source."
    """
    # Keep the difference between empty input and delimiter-only input so the
    # API and direct CLI paths can choose their own defaults.
    if not raw_value.strip():
        return None

    cleaned_values = [item.strip() for item in raw_value.split(",") if item.strip()]
    return tuple(cleaned_values)


def _parse_iso_date(raw_value: str, field_name: str) -> date:
    """Parse one ISO date and raise a 422 error on failure."""
    if len(raw_value) != 10:
        raise SearchValidationError(f"Invalid {field_name} date, expected YYYY-MM-DD")
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise SearchValidationError(
            f"Invalid {field_name} date, expected YYYY-MM-DD"
        ) from exc


def _normalize_source_names(
    source_names: Sequence[str] | None,
) -> tuple[str, ...] | None:
    """Validate requested source names and preserve order."""
    if source_names is None:
        return None

    known_sources = registered_source_names()
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_name in source_names:
        cleaned_name = raw_name.strip().lower()
        if not cleaned_name or cleaned_name in seen:
            continue

        # Show the allowed names immediately so a typo is easy to fix.
        if cleaned_name not in known_sources:
            allowed = ", ".join(sorted(known_sources))
            raise SearchValidationError(
                f"Unknown source '{cleaned_name}'. Allowed values: {allowed}"
            )
        normalized.append(cleaned_name)
        seen.add(cleaned_name)

    return tuple(normalized)


def _parse_list_field(raw_value: str, lowercase: bool = True) -> tuple[str, ...]:
    """Split and deduplicate a comma/newline-delimited field.

    Parameters
    ----------
    raw_value : str
        Raw field value from query parameters or CLI arguments.
    lowercase : bool, optional
        When ``True``, normalize values to lowercase.

    Returns
    -------
    tuple[str, ...]
        Ordered unique values with empty terms removed.
    """
    terms: list[str] = []

    # Accept both commas and newlines so API and CLI callers can provide lists
    # in the same way.
    for raw_line in raw_value.splitlines():
        for raw_term in raw_line.split(","):
            cleaned_term = raw_term.strip()
            if not cleaned_term:
                continue
            normalized_term = cleaned_term.lower() if lowercase else cleaned_term
            terms.append(normalized_term)

    return tuple(dict.fromkeys(terms))


def _normalize_newsapi_search_in(raw_value: str) -> str:
    """Validate and put NewsAPI ``searchIn`` values in a stable order.

    Parameters
    ----------
    raw_value : str
        Comma-separated NewsAPI field names from the API or CLI boundary.

    Returns
    -------
    str
        ``all`` or a comma-separated field list ordered as NewsAPI documents it.
    """
    cleaned = raw_value.strip().lower()
    if not cleaned or cleaned == "all":
        return "all"

    # Parse first, then validate, so blank and unknown fields take one clear
    # error path.
    fields = [field.strip() for field in cleaned.split(",") if field.strip()]
    has_unknown_field = any(
        field not in ALLOWED_NEWSAPI_SEARCH_IN_FIELDS for field in fields
    )
    if not fields or has_unknown_field:
        allowed = ", ".join(("all", *NEWSAPI_SEARCH_IN_FIELD_ORDER))
        raise SearchValidationError(
            f"Invalid newsapi_search_in. Allowed values: {allowed}"
        )

    # Use NewsAPI's field order even when the caller lists fields differently so
    # comparisons and caching remain stable.
    ordered_fields = [
        field for field in NEWSAPI_SEARCH_IN_FIELD_ORDER if field in fields
    ]
    return ",".join(ordered_fields)


def _validate_choice(
    value: str,
    allowed_values: set[str],
    field_name: str,
) -> str:
    """Validate an enumerated query parameter."""
    if value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        raise SearchValidationError(f"Invalid {field_name}. Allowed values: {allowed}")
    return value
