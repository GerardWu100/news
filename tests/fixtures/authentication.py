"""Build sign-in state for tests without paying for repeated hashing.

Hashing a password is deliberately slow, so the test account's hash is computed
once when this module is imported and written straight into each temporary
data directory. Tests that need to exercise the real hashing path call
:func:`news.web.credentials.sync_ui_credentials` themselves.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient

from news.api.auth import SESSION_COOKIE_NAME, LoginSessions
from news.web.auth_store import AuthStore
from news.web.passwords import hash_password
from news.web.paths import (
    CREDENTIALS_FILENAME,
    LOGIN_STATE_FILENAME,
    SESSION_STATE_FILENAME,
)

TEST_USERNAME = "tester"
TEST_PASSWORD = "correct-horse-battery-staple"
_TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


def write_test_credentials(data_directory: Path) -> Path:
    """Write ``.ui_credentials.json`` for the shared test account.

    Parameters
    ----------
    data_directory : Path
        Directory that stands in for the operator's data directory.

    Returns
    -------
    Path
        Path of the written credentials file.
    """
    credentials_file = data_directory / CREDENTIALS_FILENAME
    credentials_file.write_text(
        json.dumps({"username": TEST_USERNAME, "password_hash": _TEST_PASSWORD_HASH}),
        encoding="utf-8",
    )
    return credentials_file


def build_login_sessions(
    data_directory: Path,
    *,
    trust_forwarded_headers: bool = False,
) -> LoginSessions:
    """Return sign-in state rooted in a temporary directory.

    Parameters
    ----------
    data_directory : Path
        Directory for the credentials, session, and failed-login files.
    trust_forwarded_headers : bool, optional
        Whether proxy headers may be believed, matching the same setting on
        the application.

    Returns
    -------
    LoginSessions
        Sign-in state configured with the shared test account.
    """
    write_test_credentials(data_directory)
    return LoginSessions(
        AuthStore(
            session_file=data_directory / SESSION_STATE_FILENAME,
            login_state_file=data_directory / LOGIN_STATE_FILENAME,
        ),
        credentials_file=data_directory / CREDENTIALS_FILENAME,
        trust_forwarded_headers=trust_forwarded_headers,
    )


def basic_auth_headers(
    username: str = TEST_USERNAME,
    password: str = TEST_PASSWORD,
) -> dict[str, str]:
    """Return an HTTP Basic ``Authorization`` header for the given account."""
    encoded_credentials = base64.b64encode(f"{username}:{password}".encode()).decode(
        "ascii"
    )
    return {"Authorization": f"Basic {encoded_credentials}"}


def attach_session_cookie(client: TestClient, sessions: LoginSessions) -> str:
    """Start a session and give the client its cookie.

    This skips the sign-in form, so route tests do not pay the password
    hashing cost on every request.

    Returns
    -------
    str
        The session identifier now held by the client.
    """
    session_id = sessions.start_session()
    client.cookies.set(SESSION_COOKIE_NAME, session_id)
    return session_id
