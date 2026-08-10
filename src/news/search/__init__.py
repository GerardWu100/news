"""Public imports for the backend search package."""

from .deduplication import canonicalize_url, deduplicate_articles
from .models import SearchRequest, SearchResult
from .service import SearchExecutor, run_search
from .validation import build_search_request

__all__ = [
    "SearchExecutor",
    "SearchRequest",
    "SearchResult",
    "build_search_request",
    "canonicalize_url",
    "deduplicate_articles",
    "run_search",
]
