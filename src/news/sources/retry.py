"""Timeout and retry helpers shared by source adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx

from news.sources.settings import current_source_settings

DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_DELAY_SECONDS = 1.0


def build_timeout() -> httpx.Timeout:
    """Build an ``httpx.Timeout`` from the configured source settings.

    Returns
    -------
    httpx.Timeout
        Connection and pool limits taken from ``connect_timeout_seconds``, read
        and write limits taken from ``read_timeout_seconds``. The values are
        read on every call so a configuration change applies without restarting
        the adapters.
    """
    settings = current_source_settings()
    return httpx.Timeout(
        connect=settings.connect_timeout_seconds,
        read=settings.read_timeout_seconds,
        write=settings.read_timeout_seconds,
        pool=settings.connect_timeout_seconds,
    )


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    retries: int = DEFAULT_RETRY_ATTEMPTS,
    base_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    cooldown_check: Callable[[], None] | None = None,
    **kwargs: object,
) -> httpx.Response:
    """Issue a GET request and retry temporary failures.

    Parameters
    ----------
    client : httpx.AsyncClient
        Configured async HTTP client used for the request.
    url : str
        Full endpoint URL.
    retries : int, optional
        Non-negative number of retries after the first call.
    base_delay_seconds : float, optional
        Starting delay between retries. Each delay doubles.
    cooldown_check : Callable[[], None] | None, optional
        Optional callback that raises while the adapter is in its local pause
        after a recent rate-limit response.
    **kwargs : object
        Extra ``httpx.AsyncClient.get`` keyword arguments, such as ``params``
        or ``headers``.

    Returns
    -------
    httpx.Response
        Successful response after ``raise_for_status`` has passed.
    """
    for attempt in range(retries + 1):
        # Let adapters enforce their local pause before each request.
        if cooldown_check is not None:
            cooldown_check()

        try:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            # Retry only server failures. Client errors usually describe a bad
            # request and should be reported immediately.
            if not _is_retryable_http_status(exc.response.status_code):
                raise
            if attempt == retries:
                raise
        except (httpx.TimeoutException, httpx.ConnectError):
            # Temporary network failures are retryable until the last attempt.
            if attempt == retries:
                raise

        # Double the delay after each failed attempt: base, 2x, 4x, ...
        await asyncio.sleep(base_delay_seconds * (2**attempt))


def _is_retryable_http_status(status_code: int) -> bool:
    """Return ``True`` when an HTTP status code is worth retrying."""
    return 500 <= status_code <= 599
