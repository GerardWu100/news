"""Small helpers shared by source adapters.

It contains the pieces shared by several adapters: hostname cleanup, ISO date
trimming, and a short local pause after a source rate-limits a request.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from time import monotonic
from urllib.parse import urlparse

import httpx


def hostname_from_url(url: str) -> str:
    """Return a lowercase hostname without a leading ``www.``."""
    hostname = urlparse(url).netloc.lower()
    return hostname.removeprefix("www.")


def iso_date_prefix(value: str) -> str:
    """Return the ``YYYY-MM-DD`` prefix from an ISO-like datetime string."""
    return value[:10]


def parse_retry_after_seconds(
    raw_retry_after: str,
    *,
    default_seconds: int,
) -> int:
    """Parse ``Retry-After`` or fall back to a conservative default."""
    cleaned_value = raw_retry_after.strip()
    if cleaned_value.isdigit():
        return max(1, int(cleaned_value))
    return default_seconds


@dataclass(slots=True)
class CooldownWindow:
    """Track a short pause after a source returns HTTP 429."""

    until: float = 0.0

    def activate(self, seconds: int) -> int:
        """Start the pause and return its stored duration."""
        cooldown_seconds = max(1, seconds)
        self.until = monotonic() + cooldown_seconds
        return cooldown_seconds

    def activate_from_response(
        self,
        response: httpx.Response,
        *,
        default_seconds: int,
    ) -> int:
        """Start the pause using the response ``Retry-After`` header."""
        retry_after_seconds = parse_retry_after_seconds(
            response.headers.get("Retry-After", ""),
            default_seconds=default_seconds,
        )
        return self.activate(retry_after_seconds)

    def remaining_seconds(self) -> int:
        """Return the remaining pause in whole seconds."""
        remaining = self.until - monotonic()
        return max(0, ceil(remaining))


def raise_if_cooling(cooldown: CooldownWindow, source_label: str) -> None:
    """Stop early while a source is in its local post-429 pause.

    Parameters
    ----------
    cooldown : CooldownWindow
        Per-adapter pause state updated after HTTP 429 responses.
    source_label : str
        Source name shown in the raised ``RuntimeError`` message.
    """
    remaining_seconds = cooldown.remaining_seconds()
    if remaining_seconds <= 0:
        return

    raise RuntimeError(
        f"{source_label} is temporarily cooling down after a recent 429. "
        f"Try again in {remaining_seconds} seconds."
    )
