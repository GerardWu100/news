"""Pydantic models for responses from the public FastAPI endpoints.

These models define the data returned to the browser and CLI when they call the
configuration, source-status, and search endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FrontendConfigResponse(BaseModel):
    """Browser defaults returned by ``GET /api/config``."""

    default_english_only: bool
    default_sources: list[str]


class SourceStatusResponse(BaseModel):
    """Source descriptions and availability returned by ``GET /api/sources``."""

    name: str
    display_name: str
    description: str
    available: bool


class SearchArticleResponse(BaseModel):
    """One article in the common search format."""

    title: str
    url: str
    date: str
    source: str
    domain: str = ""
    language: str = ""
    summary: str = ""
    content: str = ""
    section: str = ""
    author: str = ""
    matched_sources: list[str] = Field(default_factory=list)
    duplicate_count: int = 1


class SourceQueryReportResponse(BaseModel):
    """Result summary for one source."""

    name: str
    display_name: str
    available: bool
    requested: bool
    returned: int
    has_more: bool = False
    error: str = ""


class SearchMetaResponse(BaseModel):
    """Search details attached to every search response."""

    query: str
    start: str
    end: str
    language: str
    deduplicate: bool
    exact_phrase: str
    exclude_terms: list[str] = Field(default_factory=list)
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)
    search_scope: str
    match_mode: str
    provider_sort: str
    section_filters: list[str] = Field(default_factory=list)
    news_desk_filters: list[str] = Field(default_factory=list)
    guardian_tags: list[str] = Field(default_factory=list)
    newsapi_search_in: str
    sort_order: str
    page: int
    has_more: bool
    has_previous: bool
    returned: int
    requested_sources: list[str] = Field(default_factory=list)
    total: int
    total_before_deduplication: int
    duplicates_removed: int
    source_reports: list[SourceQueryReportResponse] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Complete response returned by ``GET /api/search``."""

    results: list[SearchArticleResponse] = Field(default_factory=list)
    meta: SearchMetaResponse


class TrendsInterestResponse(BaseModel):
    """Search-attention series returned by ``GET /api/trends/interest``.

    Values are Google's relative index: 100 is the highest point on or before
    ``anchor_date``, and everything else is scaled against it. There are no
    absolute search counts, and a 0 can mean "below Google's reporting
    threshold" rather than "nobody searched it".
    """

    keywords: list[str] = Field(
        default_factory=list,
        description="Keywords extracted from the query; all share one scale",
    )
    start_date: str = Field(description="Inclusive window start (YYYY-MM-DD)")
    end_date: str = Field(description="Inclusive window end (YYYY-MM-DD)")
    geo: str = Field(description="Geography code; empty means worldwide")
    granularity: str = Field(
        description="Point spacing Google returned: hourly, daily, weekly, monthly"
    )
    dates: list[str] = Field(default_factory=list, description="Point labels, oldest first")
    is_partial: list[bool] = Field(
        default_factory=list,
        description="True marks a still-accumulating period, aligned with dates",
    )
    values: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Keyword to its series, aligned with dates",
    )
    anchor_date: str = Field(
        description=(
            "Last date that could contribute to the 0-100 scale. Equals "
            "end_date for a raw fetch, or the as_of date after rebasing."
        )
    )
    fetched_at: str = Field(description="UTC fetch time in ISO format")
