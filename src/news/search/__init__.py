"""Public import surface for the backend search pipeline package."""

from .deduplication import canonicalize_url, deduplicate_articles
from .models import SearchRequest, SearchResult
from .service import run_search
from .validation import build_search_request

__all__ = [
    "SearchRequest",
    "SearchResult",
    "build_search_request",
    "canonicalize_url",
    "deduplicate_articles",
    "run_search",
]
