"""Turn the operator's login settings into a stored password hash.

The operator sets ``UI_USERNAME`` and ``UI_PASSWORD``, either in ``.env`` in
the data directory or as container environment variables. On every startup
:func:`sync_ui_credentials` reads those values, hashes the password, verifies
the stored hash against the plain password, and writes the result to
``.ui_credentials.json``. Login reads only that hash file, and the operator
never runs a hashing command.

``.ui_credentials.json`` format
-------------------------------
``{"username": "<account name>", "password_hash": "pbkdf2_sha256$..."}``
written with owner-only (600) permissions.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from news.web.passwords import hash_password, verify_password
from news.web.paths import (
    CREDENTIALS_FILENAME,
    DOTENV_FILENAME,
    SESSION_STATE_FILENAME,
)

ENV_USERNAME_KEY = "UI_USERNAME"
ENV_PASSWORD_KEY = "UI_PASSWORD"
# The password shipped in .env.example. Startup warns while it is still in use.
EXAMPLE_PASSWORD = "changeme"
CREDENTIALS_FILE_PERMISSION_MODE = 0o600


def load_ui_credentials(credentials_file: Path) -> tuple[str, str] | None:
    """Load the stored account name and password hash.

    Parameters
    ----------
    credentials_file : Path
        Path to ``.ui_credentials.json``.

    Returns
    -------
    tuple[str, str] | None
        ``(username, password_hash)`` when the file holds both non-empty
        strings, otherwise ``None``. A missing or damaged file therefore
        disables login rather than raising during a request.
    """
    try:
        raw_credentials = json.loads(credentials_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw_credentials, dict):
        return None
    username = raw_credentials.get("username", "")
    password_hash = raw_credentials.get("password_hash", "")
    if not isinstance(username, str) or not isinstance(password_hash, str):
        return None
    if not username or not password_hash:
        return None
    return username, password_hash


def _write_credentials(
    credentials_file: Path,
    username: str,
    password_hash: str,
) -> None:
    """Write an owner-only credentials file through a temporary sibling."""
    credentials_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = credentials_file.with_name(f".{credentials_file.name}.tmp")
    temporary_file.write_text(
        json.dumps({"username": username, "password_hash": password_hash}) + "\n",
        encoding="utf-8",
    )
    temporary_file.chmod(CREDENTIALS_FILE_PERMISSION_MODE)
    temporary_file.replace(credentials_file)
    credentials_file.chmod(CREDENTIALS_FILE_PERMISSION_MODE)


def _revoke_existing_sessions(data_directory: Path) -> None:
    """Remove remembered sessions after the login settings change."""
    (data_directory / SESSION_STATE_FILENAME).unlink(missing_ok=True)


def sync_ui_credentials(data_directory: Path) -> str:
    """Refresh ``.ui_credentials.json`` from the environment and self-test it.

    Reads ``UI_USERNAME`` and ``UI_PASSWORD`` from the process environment,
    which a caller normally fills from ``.env`` in the data directory. When the
    stored hash already matches the current password the file is left alone,
    and that check doubles as the per-boot self-test. Otherwise a new hash is
    written, remembered sessions are dropped so the old password cannot stay
    active, and the new hash is verified before success is reported.

    Parameters
    ----------
    data_directory : Path
        Directory holding ``.env`` and ``.ui_credentials.json``.

    Returns
    -------
    str
        One status line for the startup log. Missing settings produce a
        warning line instead of an exception, so the server still starts with
        login unconfigured and every protected route closed.

    Raises
    ------
    RuntimeError
        If a freshly written hash fails verification. That indicates a bug in
        this module, never an operator mistake.
    """
    credentials_file = data_directory / CREDENTIALS_FILENAME
    username = os.getenv(ENV_USERNAME_KEY, "").strip()
    password = os.getenv(ENV_PASSWORD_KEY, "")

    if not username or not password.strip():
        credentials_file.unlink(missing_ok=True)
        _revoke_existing_sessions(data_directory)
        return (
            f"{ENV_USERNAME_KEY} or {ENV_PASSWORD_KEY} is not set; browser and "
            f"API access stay closed until both are set in "
            f"{data_directory / DOTENV_FILENAME} and the server restarts."
        )

    default_password_warning = (
        f" WARNING: {ENV_PASSWORD_KEY} is still the example value "
        f"'{EXAMPLE_PASSWORD}'; change it."
        if password == EXAMPLE_PASSWORD
        else ""
    )

    # Matching stored credentials mean there is nothing to write. Verifying the
    # stored hash against the current password on every boot is the self-test.
    stored_credentials = load_ui_credentials(credentials_file)
    if stored_credentials is not None:
        stored_username, stored_hash = stored_credentials
        if stored_username == username and verify_password(password, stored_hash):
            return (
                f"Login credentials for '{username}' verified against "
                f"{credentials_file}.{default_password_warning}"
            )

    _write_credentials(credentials_file, username, hash_password(password))
    _revoke_existing_sessions(data_directory)

    # Self-test: read back what was written and prove the hash verifies.
    written_credentials = load_ui_credentials(credentials_file)
    if written_credentials is None or not verify_password(
        password,
        written_credentials[1],
    ):
        raise RuntimeError(
            f"Credential self-test failed after writing {credentials_file}."
        )

    return (
        f"Hashed the login password for '{username}' into {credentials_file} "
        f"and passed the hash self-test.{default_password_warning}"
    )
