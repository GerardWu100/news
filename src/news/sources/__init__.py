"""Provider registry and concurrent fan-out orchestration.

The source layer owns adapter registration, source-availability reporting, and
fault-isolated fan-out execution so one failing provider cannot break the full
search response.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Sequence

import httpx

from .base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from .registry import ALL_SOURCES

logger = logging.getLogger(__name__)

__all__ = [
    "Article",
    "BaseSource",
    "SourcePageResult",
    "SourceQueryReport",
    "SourceSearchOptions",
    "get_source_status",
    "search_all_detailed",
]


@dataclass(frozen=True, slots=True)
class SourceQueryReport:
    """Per-source execution summary."""

    name: str
    display_name: str
    available: bool
    requested: bool
    returned: int
    has_more: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        """Serialize the report for the API response."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "available": self.available,
            "requested": self.requested,
            "returned": self.returned,
            "has_more": self.has_more,
            "error": self.error,
        }


def get_source_status() -> list[dict[str, object]]:
    """Return lightweight source metadata for the frontend status panel."""
    return [
        {
            "name": s.name,
            "display_name": s.display_name,
            "description": s.description,
            "available": s.is_available(),
        }
        for s in ALL_SOURCES
    ]


async def search_all_detailed(
    options: SourceSearchOptions,
    source_names: Sequence[str] | None = None,
) -> tuple[list[Article], list[SourceQueryReport]]:
    """Query selected providers concurrently and return rows plus source reports.

    Parameters
    ----------
    options : SourceSearchOptions
        Validated provider-facing query options.
    source_names : Sequence[str] | None, optional
        Explicit source-name allowlist from the caller. ``None`` means use all
        currently available adapters.

    Returns
    -------
    tuple[list[Article], list[SourceQueryReport]]
        Merged article rows and one execution report per requested source.
    """
    if source_names is not None:
        requested_names = list(dict.fromkeys(source_names))
    else:
        # Default behavior queries every currently available adapter.
        requested_names = [
            source.name for source in ALL_SOURCES if source.is_available()
        ]
    selected_sources: list[BaseSource] = []
    reports: list[SourceQueryReport] = []

    for source in ALL_SOURCES:
        # Skip adapters the caller did not request.
        requested = source.name in requested_names
        if not requested:
            continue

        # Preserve requested-but-unavailable sources in the report so callers
        # can distinguish "no results" from "missing credentials".
        if not source.is_available():
            reports.append(
                SourceQueryReport(
                    name=source.name,
                    display_name=source.display_name,
                    available=False,
                    requested=True,
                    returned=0,
                    error="Credentials missing for this source",
                )
            )
            continue
        selected_sources.append(source)

    # If every requested source is unavailable, return the reports immediately
    # without launching empty fan-out tasks.
    if not selected_sources:
        return [], reports

    tasks = [_safe_search(source, options) for source in selected_sources]
    source_pages = await asyncio.gather(*tasks)

    articles: list[Article] = []
    for source, (page, error_message) in zip(selected_sources, source_pages):
        reports.append(
            SourceQueryReport(
                name=source.name,
                display_name=source.display_name,
                available=True,
                requested=True,
                returned=len(page.articles),
                has_more=page.has_more,
                error=error_message,
            )
        )
        articles.extend(page.articles)

    return articles, reports


async def _safe_search(
    source: BaseSource,
    options: SourceSearchOptions,
) -> tuple[SourcePageResult, str]:
    """Catch per-source failures so one adapter cannot abort the fan-out."""
    try:
        page = await source.search(options)
        return page, ""
    except Exception as exc:
        logger.exception("Source %s failed", source.name)
        return SourcePageResult(articles=[], has_more=False), _format_source_error(exc)


def _format_source_error(exc: Exception) -> str:
    """Map raw adapter errors into user-facing source report messages."""
    if isinstance(exc, RuntimeError) and str(exc).strip():
        return str(exc)

    match exc:
        case httpx.TimeoutException():
            return "Request timed out while contacting this source."
        case httpx.ConnectError():
            return "Network error while contacting this source."
        case httpx.HTTPStatusError():
            status_code = exc.response.status_code
            if status_code in {401, 403}:
                return (
                    "Authentication failed for this source. Check the configured key."
                )
            if status_code == 429:
                return "Source rate limited this query. Try again later."
            if 500 <= status_code <= 599:
                return "Source server error. Try again later."
            return f"Source request failed with HTTP {status_code}."
        case _:
            return "Unexpected source error. Check server logs for details."
