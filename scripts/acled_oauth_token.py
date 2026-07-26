"""ACLED OAuth bootstrap helper for bearer-token workflows.

The script loads ACLED OAuth credentials from the project ``.env``, requests a
token payload, and persists the useful token fields back to ``.env``. It does
not save the raw OAuth response because that response contains secrets.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_TIMEOUT_SECONDS = 30
COMMON_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
COMMON_ACCEPT_LANGUAGE = "en-US,en;q=0.9"
COMMON_REFERER = "https://acleddata.com/"


@dataclass(frozen=True)
class OAuthConfig:
    """ACLED OAuth request fields."""

    token_url: str
    username: str
    password: str
    grant_type: str
    client_id: str


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE pairs from `.env`."""

    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), normalize_env_value(value.strip()))


def normalize_env_value(raw_value: str) -> str:
    """Trim matching surrounding quotes from `.env` values."""

    if len(raw_value) >= 2:
        if raw_value[0] == raw_value[-1] and raw_value[0] in {"'", '"'}:
            return raw_value[1:-1]
    return raw_value


def require_env(name: str) -> str:
    """Read a required environment variable or raise a clear error."""

    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required env variable: {name}")
    return value


def load_oauth_config() -> OAuthConfig:
    """Load and validate OAuth config from environment variables."""

    token_url = require_env("ACLED_OAUTH_TOKEN_URL")
    grant_type = require_env("ACLED_OAUTH_GRANT_TYPE")
    client_id = require_env("ACLED_OAUTH_CLIENT_ID")
    username = require_env("ACLED_USERNAME")
    password = require_env("ACLED_PASSWORD")

    if username == "your_email":
        raise ValueError("ACLED_USERNAME is still placeholder value 'your_email'.")
    if password == "your_password":
        raise ValueError("ACLED_PASSWORD is still placeholder value 'your_password'.")

    return OAuthConfig(
        token_url=token_url,
        username=username,
        password=password,
        grant_type=grant_type,
        client_id=client_id,
    )


def request_oauth_token(
    config: OAuthConfig,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Request an OAuth token from ACLED."""

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

    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def decode_http_error_body(error: HTTPError) -> str:
    """Best-effort decode of an HTTP error body."""

    try:
        body = error.read().decode("utf-8", errors="replace").strip()
    except Exception:
        body = ""
    return body


def print_acled_auth_hints(status_code: int, error_body: str) -> None:
    """Print ACLED-specific troubleshooting hints."""

    if status_code == 400:
        print(
            "Hint: ACLED docs map 400 on /oauth/token to incorrect credentials (invalid_grant)."
        )
        return

    if status_code == 401:
        print(
            "Hint: ACLED docs map 401 to invalid/denied token usage for API requests."
        )
        return

    if status_code == 403:
        print("Hint: ACLED docs list 403 causes including:")
        print("- Consent not accepted for the authenticated user.")
        print("- Required profile fields not completed.")
        print("- Access denied (missing API access group/permissions).")
        if "error code: 1010" in error_body.lower():
            print("Detected likely edge/WAF block (code 1010).")
            print("Try from a normal browser network (no VPN/proxy/datacenter IP).")
            print("If persistent, contact ACLED support with this error code.")
        if error_body:
            lowered = error_body.lower()
            if "consent" in lowered:
                print("Detected likely cause: consent requirement.")
            if "required fields" in lowered:
                print("Detected likely cause: incomplete profile fields.")
            if "access denied" in lowered:
                print("Detected likely cause: missing API access permission/group.")
        return

    if status_code == 404:
        print("Hint: ACLED docs list 404/invalid URL for incorrect endpoint paths.")


def extract_access_token(payload: dict[str, Any]) -> str | None:
    """Extract bearer token from common OAuth response key variants."""

    for key in ("access_token", "token", "accessToken"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def update_or_append_env_key(path: Path, key: str, value: str) -> None:
    """Upsert KEY=VALUE entry in .env while preserving unrelated entries."""

    lines: list[str] = []
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()

    updated = False
    new_lines: list[str] = []
    prefix = f"{key}="

    for line in lines:
        if line.strip().startswith(prefix):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        if new_lines and new_lines[-1].strip():
            new_lines.append("")
        new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def mask_secret(secret: str) -> str:
    """Mask a token for terminal display."""

    if len(secret) <= 10:
        return "*" * len(secret)
    return f"{secret[:6]}...{secret[-4:]}"


def persist_token_fields(token_payload: dict[str, Any]) -> None:
    """Persist token fields from OAuth response into root `.env`."""

    access_token = extract_access_token(token_payload)
    if access_token is None:
        raise ValueError("Token response did not contain an access token.")

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

    print(f"Stored ACLED_BEARER_TOKEN in {ENV_PATH}")
    print(f"Token preview: {mask_secret(access_token)}")
    if expires_in:
        print(f"Token expires_in (seconds): {expires_in}")
    if refresh_token:
        print(f"Refresh token preview: {mask_secret(refresh_token)}")
    print("Use this header for later requests:")
    print(f"Authorization: {token_type} <ACLED_BEARER_TOKEN>")


def main() -> None:
    """Request token and persist bearer credentials for later API usage."""

    load_env_file(ENV_PATH)

    try:
        config = load_oauth_config()
    except ValueError as error:
        print(error)
        return

    print(f"Requesting OAuth token from: {config.token_url}")

    try:
        token_payload = request_oauth_token(config=config)
    except HTTPError as error:
        error_body = decode_http_error_body(error)
        print(f"Token request failed with HTTP {error.code}.")
        if error_body:
            print(f"Response body: {error_body}")
        print_acled_auth_hints(status_code=error.code, error_body=error_body)
        print("ACLED docs:")
        print(
            "- Getting started: https://acleddata.com/api-documentation/getting-started"
        )
        print(
            "- Error messages: https://acleddata.com/api-documentation/elements-acleds-api"
        )
        return
    except URLError as error:
        print(f"Token request failed with network error: {error.reason}")
        return
    except Exception as error:
        print(f"Token request failed: {error}")
        return

    try:
        persist_token_fields(token_payload)
    except ValueError as error:
        print(error)
        return

    print("Bearer token saved. The news search provider can now use it.")


if __name__ == "__main__":
    main()
