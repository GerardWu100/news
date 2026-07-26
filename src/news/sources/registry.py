"""Source adapter registry and source-name lookup helpers."""

from __future__ import annotations

from news.sources.base import BaseSource
from news.sources.providers.acled import AcledSource
from news.sources.providers.gdelt import GdeltSource
from news.sources.providers.guardian import GuardianSource
from news.sources.providers.mediacloud import MediaCloudSource
from news.sources.providers.newsapi import NewsApiSource
from news.sources.providers.nyt import NewYorkTimesSource


def build_default_sources() -> list[BaseSource]:
    """Construct the default ordered provider adapter list.

    Returns
    -------
    list[BaseSource]
        Fresh provider adapter instances in the project-wide display order.
    """
    return [
        GdeltSource(),
        MediaCloudSource(),
        AcledSource(),
        NewYorkTimesSource(),
        GuardianSource(),
        NewsApiSource(),
    ]


ALL_SOURCES: list[BaseSource] = build_default_sources()


def source_names() -> set[str]:
    """Return the registered provider names."""
    return {source.name for source in ALL_SOURCES}
