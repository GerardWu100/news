"""Pydantic response models for public FastAPI endpoints.

These schemas define the serialized contract consumed by the browser frontend
and CLI clients when they call config, source-status, and search endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FrontendConfigResponse(BaseModel):
    """Frontend defaults returned by ``GET /api/config``."""

    default_english_only: bool
    default_sources: list[str]


class SourceStatusResponse(BaseModel):
    """Source availability metadata returned by ``GET /api/sources``."""

    name: str
    display_name: str
    description: str
    available: bool


class SearchArticleResponse(BaseModel):
    """Normalized search result row."""

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
    """Execution report for one upstream provider."""

    name: str
    display_name: str
    available: bool
    requested: bool
    returned: int
    has_more: bool = False
    error: str = ""


class SearchMetaResponse(BaseModel):
    """Top-level metadata attached to every search response."""

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
    """Complete payload returned by ``GET /api/search``."""

    results: list[SearchArticleResponse] = Field(default_factory=list)
    meta: SearchMetaResponse
