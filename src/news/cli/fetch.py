"""Fetch search responses for the command line."""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from news.search.validation import split_csv_values
from news.web.credentials import ENV_PASSWORD_KEY, ENV_USERNAME_KEY
from news.web.paths import env_path

from .parser import build_api_params

REQUEST_TIMEOUT_SECONDS = 30.0
UNAUTHORIZED_STATUS = 401


def fetch_page(args: argparse.Namespace, *, page: int) -> dict[str, Any]:
    """Fetch one page through the API or directly through the package."""
    if args.direct:
        return asyncio.run(fetch_direct_page(args, page=page))
    return fetch_api_page(args, page=page)


def api_credentials() -> tuple[str, str] | None:
    """Return the account name and password used for API requests.

    The server requires a signed-in account, and the command line proves the
    account with HTTP Basic authentication: the same two values the browser
    sign-in form takes, sent as a header on every request.

    Returns
    -------
    tuple[str, str] | None
        ``(username, password)`` when both ``UI_USERNAME`` and ``UI_PASSWORD``
        are set, otherwise ``None``. Requests are still sent without
        credentials in that case so the server, not this function, decides
        whether they are needed.
    """
    username = os.getenv(ENV_USERNAME_KEY, "").strip()
    password = os.getenv(ENV_PASSWORD_KEY, "")
    if not username or not password:
        return None
    return username, password


def build_api_client() -> httpx.Client:
    """Build the HTTP client used for every request to the news server.

    Every server route that returns news data requires the account, so the
    credentials belong on the client rather than on individual calls. Building
    the client in one place keeps the search route and the download routes from
    drifting apart.

    Returns
    -------
    httpx.Client
        Client carrying the shared timeout, redirect policy, and account.
    """
    return httpx.Client(
        timeout=REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        auth=api_credentials(),
    )


def rejected_credentials_error(server: str) -> RuntimeError:
    """Build the error shown when the server refuses the account.

    Parameters
    ----------
    server : str
        Base server address the request was sent to.

    Returns
    -------
    RuntimeError
        Message naming the two settings to fix rather than repeating the raw
        HTTP status, which does not tell the reader what to change.
    """
    return RuntimeError(
        f"{server} rejected the sign-in details. Set "
        f"{ENV_USERNAME_KEY} and {ENV_PASSWORD_KEY} in .env to the "
        "same account the server was started with."
    )


def fetch_api_page(args: argparse.Namespace, page: int) -> dict[str, Any]:
    """Fetch one source page through the running HTTP API.

    Raises
    ------
    RuntimeError
        If the server rejects the credentials.
    """
    with build_api_client() as client:
        response = client.get(
            f"{args.server.rstrip('/')}/api/search",
            params=build_api_params(args, page=page),
        )
        if response.status_code == UNAUTHORIZED_STATUS:
            raise rejected_credentials_error(args.server)
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
