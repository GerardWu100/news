"""Request an ACLED OAuth token and save it to the local `.env` file.

The reusable request, parsing, and save logic lives in
``news.sources.acled_oauth``. This wrapper loads local settings and prints
messages for the terminal.
"""

from __future__ import annotations

from pathlib import Path
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

from news.sources.acled_oauth import (
    load_oauth_config,
    mask_secret,
    obtain_and_persist_token,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


def _decode_http_error_body(error: HTTPError) -> str:
    """Decode an HTTP error response when possible for a useful error message."""
    try:
        return error.read().decode("utf-8", errors="replace").strip()
    except (AttributeError, OSError):
        return ""


def _print_acled_auth_hint(status_code: int, error_body: str) -> None:
    """Print a short ACLED hint for known HTTP status codes."""
    hints = {
        400: "Check the ACLED username and password.",
        401: "Check whether the account or token is authorized.",
        403: "Accept consent, complete the profile, and verify API access.",
        404: "Check ACLED_OAUTH_TOKEN_URL.",
    }
    if status_code in hints:
        print(f"Hint: {hints[status_code]}")
    if status_code == 403 and "error code: 1010" in error_body.lower():
        print("ACLED edge protection returned code 1010; retry without a VPN or proxy.")


def main() -> int:
    """Load local settings, request a token, and report the result."""
    load_dotenv(ENV_PATH)
    try:
        config = load_oauth_config()
    except ValueError as error:
        print(error)
        return 1

    print(f"Requesting OAuth token from: {config.token_url}")
    try:
        stored_token = obtain_and_persist_token(config, ENV_PATH)
    except HTTPError as error:
        error_body = _decode_http_error_body(error)
        print(f"Token request failed with HTTP {error.code}.")
        if error_body:
            print(f"Response body: {error_body}")
        _print_acled_auth_hint(error.code, error_body)
        return 1
    except URLError as error:
        print(f"Token request failed with network error: {error.reason}")
        return 1
    except (OSError, ValueError) as error:
        print(f"Token request failed: {error}")
        return 1

    print(f"Stored ACLED_BEARER_TOKEN in {ENV_PATH}")
    print(f"Token preview: {mask_secret(stored_token.access_token)}")
    if stored_token.expires_in:
        print(f"Token expires_in (seconds): {stored_token.expires_in}")
    if stored_token.refresh_token:
        print(f"Refresh token preview: {mask_secret(stored_token.refresh_token)}")
    print(f"Authorization: {stored_token.token_type} <ACLED_BEARER_TOKEN>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
