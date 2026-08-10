"""Request an ACLED OAuth token and save its useful fields locally.

This module handles the network request, response checks, and `.env` update.
The command wrapper supplies environment values and terminal messages. Network
and clock functions can be replaced so tests stay offline and repeatable.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO, Protocol
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 30
COMMON_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
TOKEN_KEYS = ("access_token", "token", "accessToken")


class UrlOpener(Protocol):
    """Function shape used to make the OAuth request."""

    def __call__(
        self,
        request: Request,
        *,
        timeout: int,
    ) -> AbstractContextManager[BinaryIO]:
        """Open one URL request and return a readable response."""
        ...


@dataclass(frozen=True, slots=True)
class OAuthConfig:
    """Validated ACLED OAuth request fields.

    Attributes
    ----------
    token_url : str
        Hypertext Transfer Protocol (HTTP) endpoint for token requests.
    username : str
        ACLED account email.
    password : str
        ACLED account password.
    grant_type : str
        OAuth grant type accepted by ACLED.
    client_id : str
        OAuth client identifier accepted by ACLED.
    """

    token_url: str
    username: str
    password: str
    grant_type: str
    client_id: str


@dataclass(frozen=True, slots=True)
class StoredToken:
    """Useful token fields saved for later ACLED requests.

    Attributes
    ----------
    access_token : str
        Bearer credential saved under ``ACLED_BEARER_TOKEN``.
    token_type : str
        Authorization scheme, normally ``Bearer``.
    expires_in : str
        Provider-reported lifetime in seconds, or an empty string.
    refresh_token : str
        Optional refresh credential, or an empty string.
    obtained_at_utc : str
        ISO 8601 Coordinated Universal Time (UTC) acquisition timestamp.
    """

    access_token: str
    token_type: str
    expires_in: str
    refresh_token: str
    obtained_at_utc: str


def load_oauth_config(
    environ: Mapping[str, str] | None = None,
) -> OAuthConfig:
    """Load and validate OAuth fields from an environment mapping.

    Parameters
    ----------
    environ : Mapping[str, str] | None, optional
        Environment-like key-value mapping. ``None`` uses ``os.environ``.

    Returns
    -------
    OAuthConfig
        Validated request values.

    Raises
    ------
    ValueError
        If a required value is absent or still contains an example placeholder.
    """
    active_environment = os.environ if environ is None else environ
    config = OAuthConfig(
        token_url=_require_value(active_environment, "ACLED_OAUTH_TOKEN_URL"),
        username=_require_value(active_environment, "ACLED_USERNAME"),
        password=_require_value(active_environment, "ACLED_PASSWORD"),
        grant_type=_require_value(active_environment, "ACLED_OAUTH_GRANT_TYPE"),
        client_id=_require_value(active_environment, "ACLED_OAUTH_CLIENT_ID"),
    )
    if config.username.lower().startswith("your_"):
        raise ValueError("ACLED_USERNAME still contains an example placeholder.")
    if config.password.lower().startswith("your_"):
        raise ValueError("ACLED_PASSWORD still contains an example placeholder.")
    return config


def request_oauth_token(
    config: OAuthConfig,
    *,
    opener: UrlOpener = urlopen,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Request and decode one ACLED OAuth token response.

    Parameters
    ----------
    config : OAuthConfig
        Validated request fields.
    opener : UrlOpener, optional
        Network request function. Tests may inject an offline fake.
    timeout_seconds : int, optional
        Maximum request duration in seconds.

    Returns
    -------
    dict[str, Any]
        Decoded token response dictionary.

    Raises
    ------
    ValueError
        If the timeout is invalid or the response is not a JSON object.
    urllib.error.HTTPError
        If the provider returns an HTTP error.
    urllib.error.URLError
        If the request cannot reach the provider.
    """
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    form_body = urlencode(
        {
            "username": config.username,
            "password": config.password,
            "grant_type": config.grant_type,
            "client_id": config.client_id,
        }
    ).encode("utf-8")
    request = Request(config.token_url, data=form_body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", COMMON_USER_AGENT)

    with opener(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Token response must be a JSON object.")
    return payload


def persist_token_fields(
    token_payload: Mapping[str, Any],
    env_file: Path,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> StoredToken:
    """Validate useful token fields and update one `.env` file in one write.

    Parameters
    ----------
    token_payload : Mapping[str, Any]
        Decoded provider response.
    env_file : Path
        `.env` file to update. It is created when absent.
    clock : Callable[[], datetime], optional
        Function that supplies the acquisition time. Tests may inject a fixed
        UTC time.

    Returns
    -------
    StoredToken
        Normalized values written to the `.env` file.

    Raises
    ------
    ValueError
        If no supported access-token field exists or the clock is timezone
        naive.
    """
    access_token = extract_access_token(token_payload)
    if access_token is None:
        supported_keys = ", ".join(TOKEN_KEYS)
        raise ValueError(
            f"Token response did not contain an access token. "
            f"Expected one of: {supported_keys}."
        )

    obtained_at = clock()
    if obtained_at.tzinfo is None or obtained_at.utcoffset() is None:
        raise ValueError("OAuth persistence clock must return a timezone-aware time.")
    obtained_at_utc = obtained_at.astimezone(UTC).isoformat()
    stored_token = StoredToken(
        access_token=access_token,
        token_type=_clean_optional_value(token_payload.get("token_type")) or "Bearer",
        expires_in=_clean_optional_value(token_payload.get("expires_in")),
        refresh_token=_clean_optional_value(token_payload.get("refresh_token")),
        obtained_at_utc=obtained_at_utc,
    )

    updates = {
        "ACLED_BEARER_TOKEN": stored_token.access_token,
        "ACLED_BEARER_TOKEN_TYPE": stored_token.token_type,
        "ACLED_BEARER_OBTAINED_AT_UTC": stored_token.obtained_at_utc,
    }
    if stored_token.expires_in:
        updates["ACLED_BEARER_EXPIRES_IN"] = stored_token.expires_in
    if stored_token.refresh_token:
        updates["ACLED_REFRESH_TOKEN"] = stored_token.refresh_token
    _update_env_file(env_file, updates)
    return stored_token


def obtain_and_persist_token(
    config: OAuthConfig,
    env_file: Path,
    *,
    opener: UrlOpener = urlopen,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> StoredToken:
    """Request a token and persist its useful fields.

    Parameters
    ----------
    config : OAuthConfig
        Validated ACLED request fields.
    env_file : Path
        `.env` destination for source credentials.
    opener : UrlOpener, optional
        Injectable network function.
    clock : Callable[[], datetime], optional
        Injectable acquisition clock.
    timeout_seconds : int, optional
        Maximum request duration in seconds.

    Returns
    -------
    StoredToken
        Normalized values saved for the ACLED source adapter.
    """
    payload = request_oauth_token(
        config,
        opener=opener,
        timeout_seconds=timeout_seconds,
    )
    return persist_token_fields(payload, env_file, clock=clock)


def extract_access_token(token_payload: Mapping[str, Any]) -> str | None:
    """Extract a nonblank access token from supported response-key variants."""
    for key in TOKEN_KEYS:
        value = token_payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def mask_secret(secret: str) -> str:
    """Return a terminal-safe preview of a credential."""
    if len(secret) <= 10:
        return "*" * len(secret)
    return f"{secret[:6]}...{secret[-4:]}"


def _require_value(environ: Mapping[str, str], name: str) -> str:
    """Return one required, nonblank environment value."""
    value = environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _clean_optional_value(value: object) -> str:
    """Normalize an optional scalar response field to stripped text."""
    return "" if value is None else str(value).strip()


def _update_env_file(path: Path, updates: Mapping[str, str]) -> None:
    """Update dotenv keys while preserving unrelated lines and comments."""
    existing_lines = (
        path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    )
    pending_updates = dict(updates)
    output_lines: list[str] = []

    for line in existing_lines:
        stripped_line = line.strip()
        key = stripped_line.split("=", 1)[0] if "=" in stripped_line else ""
        if key not in updates:
            output_lines.append(line)
            continue

        # Replace the first occurrence and remove duplicate definitions.
        if key in pending_updates:
            output_lines.append(f"{key}={pending_updates.pop(key)}")

    if pending_updates:
        if output_lines and output_lines[-1].strip():
            output_lines.append("")
        output_lines.extend(f"{key}={value}" for key, value in pending_updates.items())

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
