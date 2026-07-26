"""Timeout and retry helpers shared by outbound provider adapters."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx

DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 15.0
DEFAULT_RETRY_ATTEMPTS = 2
DEFAULT_RETRY_DELAY_SECONDS = 1.0


def build_timeout(
    *,
    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
    read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS,
) -> httpx.Timeout:
    """Build a consistent ``httpx.Timeout`` for adapters."""
    return httpx.Timeout(
        connect=connect_timeout_seconds,
        read=read_timeout_seconds,
        write=read_timeout_seconds,
        pool=connect_timeout_seconds,
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
    """Issue a GET request with retries for transient failures.

    Parameters
    ----------
    client : httpx.AsyncClient
        Preconfigured async HTTP client used for the outbound call.
    url : str
        Full endpoint URL to request.
    retries : int, optional
        Number of retry attempts after the first call.
    base_delay_seconds : float, optional
        Base delay for exponential backoff between retries.
    cooldown_check : Callable[[], None] | None, optional
        Optional callback that raises when the adapter is in a local cooldown
        window after a recent rate limit response.
    **kwargs : object
        Extra ``httpx.AsyncClient.get`` keyword arguments (for example
        ``params`` or ``headers``).

    Returns
    -------
    httpx.Response
        Successful response with ``raise_for_status`` already enforced.
    """
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        # Let adapters enforce local cooldown windows before each outbound call.
        if cooldown_check is not None:
            cooldown_check()

        try:
            response = await client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            # Retry only server-side failures; client-side failures should
            # surface immediately because they are usually request bugs.
            if not _is_retryable_http_status(exc.response.status_code):
                raise
            last_error = exc
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            # Transient network failures are retryable.
            last_error = exc

        is_last_attempt = attempt >= retries
        if is_last_attempt:
            break

        # Exponential backoff: base, 2x base, 4x base, ...
        await asyncio.sleep(base_delay_seconds * (2**attempt))

    if last_error is None:
        raise RuntimeError("Retry helper exhausted without capturing an error.")
    raise last_error


def _is_retryable_http_status(status_code: int) -> bool:
    """Return ``True`` when an HTTP status code is worth retrying."""
    return 500 <= status_code <= 599
