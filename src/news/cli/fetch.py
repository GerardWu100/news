"""Fetch search responses for the command line."""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

import httpx
from dotenv import load_dotenv

from news.search.validation import split_csv_values
from news.web.paths import env_path

from .parser import build_api_params


def fetch_page(args: argparse.Namespace, *, page: int) -> dict[str, Any]:
    """Fetch one page through the API or directly through the package."""
    if args.direct:
        return asyncio.run(fetch_direct_page(args, page=page))
    return fetch_api_page(args, page=page)


def fetch_api_page(args: argparse.Namespace, page: int) -> dict[str, Any]:
    """Fetch one source page through the running HTTP API."""
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(
            f"{args.server.rstrip('/')}/api/search",
            params=build_api_params(args, page=page),
        )
        response.raise_for_status()
        return response.json()


async def fetch_direct_page(
    args: argparse.Namespace,
    *,
    page: int,
) -> dict[str, Any]:
    """Fetch one source page by calling the package directly.

    The direct path loads ``.env`` from the current working directory and skips
    HTTP while using the same validation and search process as the FastAPI app.
    """
    load_dotenv(env_path())

    from news.search import build_search_request, run_search

    # Direct mode parses source lists the same way as the HTTP route so CLI and
    # server requests choose sources identically.
    request = build_search_request(
        query=args.query,
        start_date=args.start,
        end_date=args.end,
        source_names=split_csv_values(args.sources),
        language="en" if args.english else args.language,
        deduplicate=not args.no_dedupe,
        exact_phrase=args.exact_phrase,
        exclude_terms=args.exclude,
        domain_filter=args.domain,
        exclude_domains=args.exclude_domains,
        search_scope=args.scope,
        match_mode=args.match,
        provider_sort=args.provider_sort,
        section=args.section,
        news_desk=args.news_desk,
        guardian_tag=args.guardian_tag,
        newsapi_search_in=args.newsapi_search_in,
        sort_order=args.sort,
        page=page,
    )
    result = await run_search(request, use_cache=False)
    return result.to_payload()
