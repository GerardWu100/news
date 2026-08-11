"""Source registry and parallel search coordination.

The source layer registers adapters, reports availability, and isolates failures
so one source cannot stop the complete search response.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass

import httpx

from .base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from .registry import ALL_SOURCES

logger = logging.getLogger(__name__)

# Environment variables holding a provider secret. Their current values are
# removed from any provider message before it is shown to a reader.
CREDENTIAL_ENVIRONMENT_KEYS = (
    "ACLED_BEARER_TOKEN",
    "ACLED_REFRESH_TOKEN",
    "ACLED_PASSWORD",
    "GUARDIAN_API_KEY",
    "MEDIACLOUD_API_KEY",
    "NEWSAPI_API_KEY",
    "NYT_API_KEY",
    "NYT_API_SECRET",
)

# Secrets shorter than this are not redacted, because a very short value would
# match ordinary words and erase the explanation instead of protecting it.
MINIMUM_REDACTED_LENGTH = 8

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
    """Summary of one source request."""

    name: str
    display_name: str
    available: bool
    requested: bool
    returned: int
    has_more: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        """Turn the report into data for the API response."""
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
    """Return source descriptions and availability for the browser."""
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
    """Query selected sources in parallel and return articles plus reports.

    Parameters
    ----------
    options : SourceSearchOptions
        Validated options in the format source adapters expect.
    source_names : Sequence[str] | None, optional
        Explicit source names from the caller. ``None`` means use every source
        that is currently available.

    Returns
    -------
    tuple[list[Article], list[SourceQueryReport]]
        Merged articles and one report for each requested source.
    """
    if source_names is not None:
        requested_names = list(dict.fromkeys(source_names))
    else:
        # With no explicit list, query every source that is available now.
        requested_names = [
            source.name for source in ALL_SOURCES if source.is_available()
        ]
    selected_sources: list[BaseSource] = []
    reports: list[SourceQueryReport] = []

    for source in ALL_SOURCES:
        # Skip sources the caller did not request.
        requested = source.name in requested_names
        if not requested:
            continue

        # Keep unavailable requested sources in the report so callers can tell
        # the difference between "no results" and "missing credentials".
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

    # If every requested source is unavailable, return without starting empty
    # tasks.
    if not selected_sources:
        return [], reports

    tasks = [_safe_search(source, options) for source in selected_sources]
    source_pages = await asyncio.gather(*tasks)

    articles: list[Article] = []
    # gather() keeps task order. strict=True turns a future length mismatch into
    # an error instead of silently dropping a source from the reports.
    for source, (page, error_message) in zip(
        selected_sources, source_pages, strict=True
    ):
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
    """Catch one source failure so it cannot stop the other searches.

    The failure is logged without the exception text. Several sources take
    their key as a query parameter, so the request URL that an HTTP error
    carries would otherwise write that key into the log file.
    """
    try:
        page = await source.search(options)
        return page, ""
    except Exception as exc:
        logger.warning(
            "Source %s failed: %s (%s)",
            source.name,
            type(exc).__name__,
            _redacted_failure_detail(exc),
        )
        return SourcePageResult(articles=[], has_more=False), _format_source_error(exc)


def _redacted_failure_detail(exc: Exception) -> str:
    """Describe one adapter failure without repeating any credential.

    Parameters
    ----------
    exc : Exception
        Failure raised by a source adapter.

    Returns
    -------
    str
        The HTTP status and the request address with its query string removed,
        or a short description when the failure carries no request.
    """
    # An adapter that replaced a provider error with a clearer message keeps
    # the original as __cause__. Follow that chain, or the log loses the status
    # code that says which provider rule was broken.
    carrier = _exception_carrying_the_request(exc)
    request_url = getattr(getattr(carrier, "request", None), "url", None)
    if request_url is None:
        return "no request details"

    # Keep only scheme, host, and path. Every provider key this project sends
    # travels in the query string or in a header, so neither survives here.
    safe_address = str(httpx.URL(request_url).copy_with(query=None, fragment=None))
    response = getattr(carrier, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is None:
        return safe_address
    return f"HTTP {status_code} from {safe_address}"


def _exception_carrying_the_request(exc: BaseException) -> BaseException | None:
    """Return the first exception in the cause chain that holds a request."""
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if getattr(current, "request", None) is not None:
            return current
        seen.add(id(current))
        current = current.__cause__
    return None


def _format_source_error(exc: Exception) -> str:
    """Turn adapter errors into short messages for the source report.

    Failed requests are worth more than a status number. A provider usually
    explains the refusal in the response body: NewsAPI names the earliest date
    the current plan allows, MediaCloud names the parameter it wanted. That
    text is appended so the reader can act without opening the server log.
    """
    if isinstance(exc, RuntimeError) and str(exc).strip():
        return str(exc)

    match exc:
        case httpx.ConnectTimeout():
            # Separate from a read timeout because the causes differ: this one
            # means the connection or TLS handshake did not finish in time.
            return (
                "Could not open a connection to this source in time. "
                "Raise sources.connect_timeout_seconds if the provider is "
                "simply slow to answer."
            )
        case httpx.TimeoutException():
            return (
                "This source accepted the request but did not answer in time. "
                "Raise sources.read_timeout_seconds or narrow the search."
            )
        case httpx.ConnectError():
            return "Network error while contacting this source."
        case httpx.HTTPStatusError():
            return _format_http_status_error(exc)
        case _:
            return "Unexpected source error. Check server logs for details."


def _format_http_status_error(exc: httpx.HTTPStatusError) -> str:
    """Describe one rejected HTTP request, including the provider's reason."""
    status_code = exc.response.status_code
    if status_code in {401, 403}:
        summary = "Authentication failed for this source. Check the configured key."
    elif status_code == 429:
        summary = "Source rate limited this query. Try again later."
    elif 500 <= status_code <= 599:
        summary = "Source server error. Try again later."
    else:
        summary = f"Source request failed with HTTP {status_code}."

    detail = _provider_explanation(exc.response)
    return f"{summary} Provider said: {detail}" if detail else summary


def _provider_explanation(response: httpx.Response, max_characters: int = 300) -> str:
    """Pull a short human-readable reason out of a provider response body.

    Only the body is read, never the request. A provider that echoed the
    request address back would still repeat the key, so every configured
    credential is removed from the text before it is returned.

    Parameters
    ----------
    response : httpx.Response
        Response that carried the failing status code.
    max_characters : int, optional
        Longest message kept, so one provider cannot flood the report.

    Returns
    -------
    str
        The provider's message, or the empty string when the body holds no
        readable explanation.
    """
    # Every caller passes a response from a completed request, so the body is
    # already in memory and decoding it replaces bad bytes rather than raising.
    body = response.text
    if not body.strip():
        return ""

    # Providers disagree on the field name for the same idea: NewsAPI uses
    # "message", MediaCloud uses "note", FastAPI-style services use "detail".
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        for field_name in ("message", "note", "detail", "error", "error_message"):
            value = payload.get(field_name)
            if isinstance(value, str) and value.strip():
                return _condense(value, max_characters)
        return ""

    # Plain-text refusals, such as GDELT's rate-limit notice, arrive without
    # any structure at all. A generic HTML error page is skipped instead,
    # because its markup would fill the report without explaining anything.
    content_type = response.headers.get("content-type", "")
    if "html" in content_type or body.lstrip()[:1] == "<":
        return ""
    return _condense(body, max_characters)


def _condense(text: str, max_characters: int) -> str:
    """Redact credentials, collapse whitespace, and trim to one readable line."""
    cleaned = " ".join(_redact_credentials(text).split())
    if len(cleaned) <= max_characters:
        return cleaned
    return f"{cleaned[: max_characters - 3].rstrip()}..."


def _redact_credentials(text: str) -> str:
    """Replace any configured credential value found in provider text.

    Source keys are read from the environment at request time, so the current
    values are known here. A provider that quotes the request back, or names
    the rejected token, would otherwise publish the secret to the browser and
    to every command-line reader.

    Short values are skipped because a one- or two-character secret would match
    ordinary prose and blank out most of the message.
    """
    redacted = text
    for variable_name in CREDENTIAL_ENVIRONMENT_KEYS:
        secret = os.getenv(variable_name, "")
        if len(secret) >= MINIMUM_REDACTED_LENGTH and secret in redacted:
            redacted = redacted.replace(secret, f"<{variable_name}>")
    return redacted
