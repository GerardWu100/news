"""Adapter for the ACLED conflict-event feed."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx

from news.sources.base import Article, BaseSource, SourcePageResult, SourceSearchOptions
from news.sources.common import iso_date_prefix
from news.sources.retry import build_timeout, get_with_retry

ACLED_PAGE_SIZE = 50
ACLED_UNAUTHORIZED_STATUSES = frozenset({401, 403})
ACLED_TOKEN_COMMAND = "uv run python scripts/acled_oauth_token.py"


class AcledSource(BaseSource):
    """Read conflict events from the ACLED API."""

    name = "acled"
    display_name = "ACLED"
    description = "Conflict and protest event database (bearer token required)"

    _BASE_URL = "https://acleddata.com/api/acled/read"

    def is_available(self) -> bool:
        """Return ``True`` when ``ACLED_BEARER_TOKEN`` is set."""
        return bool(os.getenv("ACLED_BEARER_TOKEN"))

    async def search(
        self,
        options: SourceSearchOptions,
    ) -> SourcePageResult:
        """Read one page of ACLED event records."""
        if options.page > 1:
            return SourcePageResult(articles=[], has_more=False)

        token = os.getenv("ACLED_BEARER_TOKEN", "")

        headers = {"Authorization": f"Bearer {token}"}

        params = {
            "event_date": f"{options.start_date}|{options.end_date}",
            "event_date_where": "BETWEEN",
            "terms": options.query,
            "limit": str(ACLED_PAGE_SIZE),
        }

        try:
            async with httpx.AsyncClient(timeout=build_timeout()) as client:
                resp = await get_with_retry(
                    client,
                    self._BASE_URL,
                    headers=headers,
                    params=params,
                )
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            # ACLED issues short-lived tokens, so a refusal here is far more
            # often an expired token than a wrong one. Say which, and say what
            # to run, instead of leaving the reader to guess.
            if exc.response.status_code in ACLED_UNAUTHORIZED_STATUSES:
                raise RuntimeError(_expired_token_message()) from exc
            raise

        raw_events = data.get("data") or []
        articles = [self._to_article(e) for e in raw_events]
        has_more = len(raw_events) >= ACLED_PAGE_SIZE
        return SourcePageResult(articles=articles, has_more=has_more)

    @staticmethod
    def _to_article(raw: dict) -> Article:
        """Convert one ACLED event to the common ``Article`` format."""
        event_type = raw.get("event_type", "")
        notes = raw.get("notes", "")
        title = f"[{event_type}] {notes}" if event_type else notes

        return Article(
            title=title,
            url=raw.get("source_url", ""),
            # Store only YYYY-MM-DD even if ACLED changes the rest of its date
            # formatting.
            date=iso_date_prefix(raw.get("event_date", "")),
            source="acled",
            domain=raw.get("source", ""),
            language="",
        )


def _expired_token_message() -> str:
    """Explain a refused ACLED request and name the command that fixes it.

    The token generator records when the token was issued and how many seconds
    it lasts. When both values are readable, the message states the expiry date
    so the reader can tell an expired token from a wrong one.

    Returns
    -------
    str
        One sentence about the token followed by the command to regenerate it.
    """
    expiry = _recorded_token_expiry()
    if expiry is None:
        return (
            "ACLED refused this token. Generate a new one with: "
            f"{ACLED_TOKEN_COMMAND}"
        )
    if expiry <= datetime.now(UTC):
        return (
            f"The ACLED token expired on {expiry.date().isoformat()}. "
            f"Generate a new one with: {ACLED_TOKEN_COMMAND}"
        )
    # ACLED answers a refused request with a web page rather than a reason, so
    # a token that has not expired yet leaves two candidates worth naming.
    return (
        "ACLED refused this token even though it is recorded as valid until "
        f"{expiry.date().isoformat()}. The account request limit may be "
        "reached, or the token may have been replaced. Generate a new one "
        f"with: {ACLED_TOKEN_COMMAND}"
    )


def _recorded_token_expiry() -> datetime | None:
    """Return when the stored ACLED token expires, or ``None`` if unknown."""
    obtained_at = os.getenv("ACLED_BEARER_OBTAINED_AT_UTC", "").strip()
    lifetime_seconds = os.getenv("ACLED_BEARER_EXPIRES_IN", "").strip()
    if not obtained_at or not lifetime_seconds:
        return None

    try:
        issued = datetime.fromisoformat(obtained_at)
        lifetime = float(lifetime_seconds)
    except ValueError:
        return None

    # A token generator that omitted the time zone still records UTC.
    if issued.tzinfo is None:
        issued = issued.replace(tzinfo=UTC)
    return issued + timedelta(seconds=lifetime)
