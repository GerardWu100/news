"""Shared data models and adapter interfaces for source integrations.

Every provider adapter converts upstream responses into the ``Article`` schema
so downstream filtering, deduplication, and export code stay source-agnostic.
"""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Article:
    """Normalized article or event record."""

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

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly ``dict``."""
        data = asdict(self)
        data["matched_sources"] = list(self.matched_sources or (self.source,))
        return data


@dataclass(frozen=True, slots=True)
class SourceSearchOptions:
    """Normalized provider-facing search options."""

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
    """One provider page of results plus pagination state."""

    articles: list[Article]
    has_more: bool


class BaseSource(abc.ABC):
    """Interface every source adapter must implement."""

    name: str
    display_name: str
    description: str

    @abc.abstractmethod
    async def search(
        self,
        options: SourceSearchOptions,
    ) -> SourcePageResult:
        """Search this source with normalized provider options."""
        ...

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the required credentials / config exist."""
        ...
