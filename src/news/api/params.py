"""HTTP query parameter parsing for news search routes."""

from __future__ import annotations

from fastapi import Query

from news.search import build_search_request
from news.search.validation import split_csv_values
from news.search.models import SearchRequest


class SearchQueryParams:
    """Dependency object for the public search query parameters."""

    def __init__(
        self,
        q: str = Query(..., description="Keyword or boolean query"),
        start: str = Query(..., description="Start date (YYYY-MM-DD)"),
        end: str = Query(..., description="End date (YYYY-MM-DD)"),
        sources: str = Query(
            default="",
            description="Comma-separated source names (default: all available)",
        ),
        language: str = Query(
            default="",
            description=(
                "Language filter such as 'en', 'english', or 'en-US'. "
                "Provider labels are normalized before comparison."
            ),
        ),
        dedupe: bool = Query(
            default=True,
            description="Collapse duplicate articles that appear across sources",
        ),
        exact_phrase: str = Query(
            default="",
            description="Optional exact phrase to require in post-filtering",
        ),
        exclude_terms: str = Query(
            default="",
            description="Comma-separated terms to exclude from results",
        ),
        domain: str = Query(
            default="",
            description="Comma-separated domains to include in local filtering",
        ),
        exclude_domains: str = Query(
            default="",
            description="Comma-separated domains to exclude from local filtering",
        ),
        search_scope: str = Query(
            default="all",
            description="Local filter scope: 'all' or 'title'",
        ),
        match_mode: str = Query(
            default="provider",
            description="Keyword post-filter mode: 'provider', 'all_terms', or 'any_term'",
        ),
        provider_sort: str = Query(
            default="default",
            description="Upstream provider ranking mode where supported",
        ),
        section: str = Query(
            default="",
            description="Comma-separated section filters for providers that support them",
        ),
        news_desk: str = Query(
            default="",
            description="Comma-separated New York Times news desk filters",
        ),
        guardian_tag: str = Query(
            default="",
            description="Comma-separated Guardian tags such as business/economics",
        ),
        newsapi_search_in: str = Query(
            default="all",
            description="NewsAPI field scope for q: all, title, description, content",
        ),
        sort: str = Query(
            default="date_desc",
            description="Sort order: 'date_desc' or 'date_asc'",
        ),
        page: int = Query(
            default=1,
            ge=1,
            description="1-based provider page number",
        ),
    ) -> None:
        self.q = q
        self.start = start
        self.end = end
        self.sources = sources
        self.language = language
        self.dedupe = dedupe
        self.exact_phrase = exact_phrase
        self.exclude_terms = exclude_terms
        self.domain = domain
        self.exclude_domains = exclude_domains
        self.search_scope = search_scope
        self.match_mode = match_mode
        self.provider_sort = provider_sort
        self.section = section
        self.news_desk = news_desk
        self.guardian_tag = guardian_tag
        self.newsapi_search_in = newsapi_search_in
        self.sort = sort
        self.page = page

    def to_search_request(self) -> SearchRequest:
        """Convert query parameters into the validated search request."""
        return build_search_request(
            query=self.q,
            start_date=self.start,
            end_date=self.end,
            source_names=split_csv_values(self.sources),
            language=self.language,
            deduplicate=self.dedupe,
            exact_phrase=self.exact_phrase,
            exclude_terms=self.exclude_terms,
            domain_filter=self.domain,
            exclude_domains=self.exclude_domains,
            search_scope=self.search_scope,
            match_mode=self.match_mode,
            provider_sort=self.provider_sort,
            section=self.section,
            news_desk=self.news_desk,
            guardian_tag=self.guardian_tag,
            newsapi_search_in=self.newsapi_search_in,
            sort_order=self.sort,
            page=self.page,
        )
