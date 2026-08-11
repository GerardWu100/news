"""Fetch search responses for the command line."""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from news.search.validation import split_csv_values
from news.sources.settings import configure_sources
from news.web.config import load_settings
from news.web.credentials import ENV_PASSWORD_KEY, ENV_USERNAME_KEY
from news.web.paths import env_path

from .parser import build_api_params

REQUEST_TIMEOUT_SECONDS = 30.0
UNAUTHORIZED_STATUS = 401

# Longest server explanation repeated to the reader, so a proxy error page
# cannot fill the terminal.
SERVER_EXPLANATION_LIMIT = 300


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


def rejected_request_error(response: httpx.Response) -> RuntimeError:
    """Build the error shown when the server refuses a search.

    The server states why it refused: which date is wrong, which source name it
    does not know. Reporting only the status code throws that sentence away and
    leaves the reader with a number and the full request address, which is both
    long and silent about what to change.

    Parameters
    ----------
    response : httpx.Response
        Response that carried the refusing status code.

    Returns
    -------
    RuntimeError
        The server's own explanation when it sent one, otherwise the status.
    """
    explanation = server_explanation(response)
    if explanation:
        return RuntimeError(
            f"The server refused this search (HTTP {response.status_code}): "
            f"{explanation}"
        )
    return RuntimeError(
        f"The server refused this search with HTTP {response.status_code}."
    )


def server_explanation(response: httpx.Response) -> str:
    """Pull the readable reason out of a refused server response.

    Two shapes arrive. A route that rejects a search on purpose sends
    ``{"detail": "Start date must be on or before end date"}``. A query
    parameter that fails automatic validation sends ``detail`` as a list of
    entries, each with its own ``msg`` and the parameter name in ``loc``.

    Parameters
    ----------
    response : httpx.Response
        Response that carried the refusing status code.

    Returns
    -------
    str
        One readable line, or the empty string when the body explains nothing.
    """
    try:
        payload = response.json()
    except ValueError:
        return ""

    if not isinstance(payload, dict):
        return ""

    detail = payload.get("detail")
    if isinstance(detail, str):
        return _one_line(detail)
    if isinstance(detail, list):
        return _one_line("; ".join(_validation_entry(item) for item in detail))
    return ""


def _validation_entry(item: object) -> str:
    """Describe one automatic validation failure, naming the parameter."""
    if not isinstance(item, dict):
        return str(item)
    message = str(item.get("msg", "")).strip()
    location = item.get("loc")
    # "loc" reads like ["query", "start"]; the last element is the parameter.
    if isinstance(location, list) and location:
        return f"{location[-1]}: {message}" if message else str(location[-1])
    return message


def _one_line(text: str) -> str:
    """Collapse whitespace and trim, so one message cannot fill the terminal."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= SERVER_EXPLANATION_LIMIT:
        return collapsed
    return f"{collapsed[: SERVER_EXPLANATION_LIMIT - 3].rstrip()}..."


def fetch_api_page(args: argparse.Namespace, page: int) -> dict[str, Any]:
    """Fetch one source page through the running HTTP API.

    Raises
    ------
    RuntimeError
        If the server rejects the credentials or refuses the search.
    """
    with build_api_client() as client:
        response = client.get(
            f"{args.server.rstrip('/')}/api/search",
            params=build_api_params(args, page=page),
        )
        if response.status_code == UNAUTHORIZED_STATUS:
            raise rejected_credentials_error(args.server)
        if response.is_error:
            raise rejected_request_error(response)
        return response.json()


async def fetch_direct_page(
    args: argparse.Namespace,
    *,
    page: int,
) -> dict[str, Any]:
    """Fetch one source page by calling the package directly.

    The direct path loads ``.env`` from the current working directory and skips
    HTTP while using the same validation and search process as the FastAPI app.
    Source settings are installed here for the same reason the server installs
    them at startup: adapters read them instead of receiving them per call.
    """
    load_dotenv(env_path())
    configure_sources(load_settings(args.config).sources)

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
