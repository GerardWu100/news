"""Shared data models and interfaces for source adapters.

Each adapter converts its source response into the common ``Article`` format so
filters, duplicate removal, and exports do not need source-specific code.
"""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Article:
    """Article or event record in the common format."""

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
    matched_sources: tuple[str, ...] = ()
    duplicate_count: int = 1

    @property
    def effective_sources(self) -> tuple[str, ...]:
        """Return the sources represented by this record.

        ``matched_sources`` stays empty until deduplication merges a record, so
        an unmerged article reports the one source that supplied it. Keeping
        this rule here prevents callers from interpreting the empty tuple
        differently.
        """
        return self.matched_sources or (self.source,)

    def to_dict(self) -> dict[str, Any]:
        """Convert to a JSON-friendly dictionary."""
        data = asdict(self)
        data["matched_sources"] = list(self.effective_sources)
        return data


@dataclass(frozen=True, slots=True)
class SourceSearchOptions:
    """Search options in the format source adapters expect."""

    query: str
    start_date: str
    end_date: str
    page: int = 1
    language: str = ""
    provider_sort: str = "default"
    include_domains: tuple[str, ...] = ()
    exclude_domains: tuple[str, ...] = ()
    section_filters: tuple[str, ...] = ()
    news_desk_filters: tuple[str, ...] = ()
    guardian_tags: tuple[str, ...] = ()
    newsapi_search_in: str = "all"


@dataclass(frozen=True, slots=True)
class SourcePageResult:
    """One source page of results and its pagination state."""

    articles: list[Article]
    has_more: bool


class BaseSource(abc.ABC):
    """Base interface required of every source adapter."""

    name: str
    display_name: str
    description: str

    @abc.abstractmethod
    async def search(
        self,
        options: SourceSearchOptions,
    ) -> SourcePageResult:
        """Search this source with common search options."""
        ...

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` when the required credentials or settings exist."""
        ...
