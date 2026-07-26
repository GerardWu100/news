"""ACLED bearer-authenticated data read helper.

This script runs a sample ACLED data read request with the bearer token stored
in the project ``.env``. On ``401`` responses, it can refresh the token using
``ACLED_REFRESH_TOKEN`` and retry once.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from acled_oauth_token import (
    ENV_PATH,
    OUTPUTS_DIR,
    decode_http_error_body,
    load_env_file,
    mask_secret,
    normalize_env_value,
    print_acled_auth_hints,
    save_json,
    update_or_append_env_key,
)


ACLED_DATA_ENDPOINT = "https://acleddata.com/api/acled/read"
OUTPUT_PATH = OUTPUTS_DIR / "acled_bearer_sample_response.json"
DEFAULT_TIMEOUT_SECONDS = 30
COMMON_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
COMMON_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
COMMON_REFERER = "https://acleddata.com/"

SAMPLE_QUERY_PARAMS: dict[str, str] = {
    "limit": "10",
    "country": "Ukraine",
    "event_date": "2025-01-01|2025-01-31",
}


def require_env(name: str) -> str:
    """Read a required environment variable."""

    value = normalize_env_value(os.getenv(name, "").strip())
    if not value:
        raise ValueError(f"Missing required env variable: {name}")
    return value


def request_data_with_bearer(
    token: str,
    token_type: str,
    query_params: dict[str, str],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Execute one ACLED data read request using bearer auth."""

    request_url = f"{ACLED_DATA_ENDPOINT}?{urlencode(query_params)}"
    request = Request(request_url, method="GET")
    request.add_header("Authorization", f"{token_type} {token}")
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", COMMON_USER_AGENT)
    request.add_header("Accept-Language", COMMON_ACCEPT_LANGUAGE)
    request.add_header("Referer", COMMON_REFERER)

    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def refresh_access_token(
    token_url: str,
    client_id: str,
    refresh_token: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Request a new access token with the refresh-token flow."""

    form_body = urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")

    request = Request(token_url, data=form_body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", COMMON_USER_AGENT)

    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def persist_refreshed_token(token_payload: dict[str, Any]) -> tuple[str, str]:
    """Persist refreshed token fields to `.env` and return token plus type."""

    access_token = str(token_payload.get("access_token", "")).strip()
    if not access_token:
        raise ValueError("Refresh response did not contain access_token.")

    token_type = str(token_payload.get("token_type", "Bearer")).strip() or "Bearer"
    expires_in = str(token_payload.get("expires_in", "")).strip()
    refresh_token = str(token_payload.get("refresh_token", "")).strip()
    obtained_at = datetime.now(timezone.utc).isoformat()

    update_or_append_env_key(ENV_PATH, "ACLED_BEARER_TOKEN", access_token)
    update_or_append_env_key(ENV_PATH, "ACLED_BEARER_TOKEN_TYPE", token_type)
    if expires_in:
        update_or_append_env_key(ENV_PATH, "ACLED_BEARER_EXPIRES_IN", expires_in)
    if refresh_token:
        update_or_append_env_key(ENV_PATH, "ACLED_REFRESH_TOKEN", refresh_token)
    update_or_append_env_key(ENV_PATH, "ACLED_BEARER_OBTAINED_AT_UTC", obtained_at)

    print("Refreshed bearer token and updated root .env")
    print(f"New token preview: {mask_secret(access_token)}")
    if expires_in:
        print(f"New expires_in (seconds): {expires_in}")
    return access_token, token_type


def print_response_summary(payload: dict[str, Any]) -> None:
    """Print a compact summary of returned ACLED records."""

    records = (
        payload.get("data") or payload.get("results") or payload.get("events") or []
    )
    print(f"Returned records: {len(records)}")
    for index, record in enumerate(records[:5], start=1):
        event_date = record.get("event_date", "<missing event_date>")
        country = record.get("country", "<missing country>")
        event_type = record.get("event_type", "<missing event_type>")
        print(f"{index}. {event_date} | {country} | {event_type}")


def _report_http_error(error: HTTPError, *, context: str) -> None:
    """Print one HTTP failure with ACLED auth hints when available."""

    error_body = decode_http_error_body(error)
    print(f"{context} failed with HTTP {error.code}.")
    if error_body:
        print(f"Response body: {error_body}")
    print_acled_auth_hints(status_code=error.code, error_body=error_body)


def fetch_payload_with_optional_refresh(
    bearer_token: str,
    token_type: str,
    query_params: dict[str, str],
) -> dict[str, Any] | None:
    """Fetch ACLED data and refresh the bearer token once on HTTP 401."""

    try:
        return request_data_with_bearer(
            token=bearer_token,
            token_type=token_type,
            query_params=query_params,
        )
    except HTTPError as error:
        _report_http_error(error, context="Bearer data request")
        if error.code != 401:
            return None

    refresh_token = normalize_env_value(os.getenv("ACLED_REFRESH_TOKEN", "").strip())
    token_url = normalize_env_value(os.getenv("ACLED_OAUTH_TOKEN_URL", "").strip())
    client_id = normalize_env_value(os.getenv("ACLED_OAUTH_CLIENT_ID", "").strip())
    if not refresh_token or not token_url or not client_id:
        print("Missing ACLED_REFRESH_TOKEN or OAuth settings; cannot refresh token.")
        return None

    print("Attempting refresh-token flow...")
    try:
        refreshed_payload = refresh_access_token(
            token_url=token_url,
            client_id=client_id,
            refresh_token=refresh_token,
        )
        bearer_token, token_type = persist_refreshed_token(refreshed_payload)
    except HTTPError as refresh_error:
        _report_http_error(refresh_error, context="Refresh flow")
        return None
    except URLError as refresh_error:
        print(f"Refresh flow network error: {refresh_error.reason}")
        return None
    except Exception as refresh_error:
        print(f"Refresh flow failed: {refresh_error}")
        return None

    try:
        return request_data_with_bearer(
            token=bearer_token,
            token_type=token_type,
            query_params=query_params,
        )
    except HTTPError as error:
        _report_http_error(error, context="Bearer data request after refresh")
        return None
    except URLError as error:
        print(f"Bearer data request failed with network error: {error.reason}")
        return None
    except Exception as error:
        print(f"Bearer data request failed: {error}")
        return None


def main() -> None:
    """Run a bearer-authenticated ACLED read with optional refresh fallback."""

    load_env_file(ENV_PATH)

    try:
        bearer_token = require_env("ACLED_BEARER_TOKEN")
        token_type = (
            normalize_env_value(os.getenv("ACLED_BEARER_TOKEN_TYPE", "Bearer").strip())
            or "Bearer"
        )
    except ValueError as error:
        print(error)
        print("Run token script first:")
        print("uv run python 'API explorer/acled/acled_oauth_token.py'")
        return

    print("Using bearer token:")
    print(f"{token_type} {mask_secret(bearer_token)}")
    print(f"Request endpoint: {ACLED_DATA_ENDPOINT}")

    payload = fetch_payload_with_optional_refresh(
        bearer_token=bearer_token,
        token_type=token_type,
        query_params=SAMPLE_QUERY_PARAMS,
    )
    if payload is None:
        return

    print("Bearer data request succeeded.")
    save_json(OUTPUT_PATH, payload)
    print_response_summary(payload)
    print(f"Saved bearer sample response: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
