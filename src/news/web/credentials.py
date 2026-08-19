"""Turn the operator's login settings into stored password hashes.

The operator sets up to :data:`MAX_ACCOUNTS` sign-in accounts, either in
``.env`` in the data directory or as container environment variables. The
first account uses ``UI_USERNAME`` and ``UI_PASSWORD``; the second and third
add a slot number, so ``UI_USERNAME_2`` with ``UI_PASSWORD_2`` and
``UI_USERNAME_3`` with ``UI_PASSWORD_3``. Slots left blank are ignored, and
every account has the same rights: there is no owner or guest level here.

On every startup :func:`sync_ui_credentials` reads those values, hashes each
password, verifies the stored hashes against the plain passwords, and writes
the result to ``.ui_credentials.json``. Sign-in reads only that hash file, and
the operator never runs a hashing command.

``.ui_credentials.json`` format
-------------------------------
``{"accounts": [{"username": "<account name>", "password_hash":
"pbkdf2_sha256$..."}, ...]}`` written with owner-only (600) permissions. The
accounts keep the slot order of the settings, so the first account is the one
from ``UI_USERNAME``.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path
from typing import NamedTuple

from news.web.file_locks import locked_text_file
from news.web.passwords import hash_password, verify_password
from news.web.paths import (
    CREDENTIALS_FILENAME,
    DOTENV_FILENAME,
    SESSION_STATE_FILENAME,
)

ENV_USERNAME_KEY = "UI_USERNAME"
ENV_PASSWORD_KEY = "UI_PASSWORD"
# How many sign-in accounts the settings may define. Slot 1 uses the plain
# keys; later slots append their number to both key names.
MAX_ACCOUNTS = 3
# The password shipped in .env.example. Startup warns while it is still in use.
EXAMPLE_PASSWORD = "changeme"
CREDENTIALS_FILE_PERMISSION_MODE = 0o600


class StoredAccount(NamedTuple):
    """One sign-in account as it is kept on disk.

    Attributes
    ----------
    username : str
        Account name typed into the sign-in form or sent in an HTTP Basic
        header.
    password_hash : str
        PBKDF2 hash of that account's password, in the format written by
        :func:`news.web.passwords.hash_password`.
    """

    username: str
    password_hash: str


def account_env_keys(slot: int) -> tuple[str, str]:
    """Return the settings key names for one account slot.

    Parameters
    ----------
    slot : int
        1-based account number, from 1 to :data:`MAX_ACCOUNTS`.

    Returns
    -------
    tuple[str, str]
        ``(username key, password key)``. Slot 1 is ``("UI_USERNAME",
        "UI_PASSWORD")``; slot 2 is ``("UI_USERNAME_2", "UI_PASSWORD_2")``.
    """
    if slot == 1:
        return ENV_USERNAME_KEY, ENV_PASSWORD_KEY
    return f"{ENV_USERNAME_KEY}_{slot}", f"{ENV_PASSWORD_KEY}_{slot}"


def read_configured_accounts() -> tuple[list[tuple[str, str]], list[str]]:
    """Collect the account name and password pairs set in the environment.

    Returns
    -------
    tuple[list[tuple[str, str]], list[str]]
        The accounts in slot order as ``(username, plain password)`` pairs,
        and a list of complaints about slots that were skipped. A slot is
        skipped when only one of its two values is set, or when its account
        name repeats one already accepted, because two accounts sharing a name
        would make the second unreachable.
    """
    accounts: list[tuple[str, str]] = []
    complaints: list[str] = []
    for slot in range(1, MAX_ACCOUNTS + 1):
        username_key, password_key = account_env_keys(slot)
        username = os.getenv(username_key, "").strip()
        password = os.getenv(password_key, "")
        if not username and not password.strip():
            continue
        if not username or not password.strip():
            complaints.append(
                f"{username_key} and {password_key} must both be set; "
                f"that account is ignored."
            )
            continue
        if any(username == accepted_name for accepted_name, _ in accounts):
            complaints.append(
                f"{username_key} repeats an account name already in use; "
                f"that account is ignored."
            )
            continue
        accounts.append((username, password))
    return accounts, complaints


def load_ui_accounts(credentials_file: Path) -> list[StoredAccount]:
    """Load the stored accounts and their password hashes.

    Parameters
    ----------
    credentials_file : Path
        Path to ``.ui_credentials.json``.

    Returns
    -------
    list[StoredAccount]
        Accounts holding a non-empty name and hash, in stored order. A
        missing, damaged, or empty file gives an empty list, which disables
        sign-in rather than raising during a request.
    """
    try:
        raw_credentials = json.loads(credentials_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw_credentials, dict):
        return []
    raw_accounts = raw_credentials.get("accounts", [])
    if not isinstance(raw_accounts, list):
        return []

    accounts: list[StoredAccount] = []
    for raw_account in raw_accounts:
        if not isinstance(raw_account, dict):
            continue
        username = raw_account.get("username", "")
        password_hash = raw_account.get("password_hash", "")
        if not isinstance(username, str) or not isinstance(password_hash, str):
            continue
        if not username or not password_hash:
            continue
        accounts.append(StoredAccount(username, password_hash))
    return accounts


def _write_credentials(
    credentials_file: Path,
    accounts: list[StoredAccount],
) -> None:
    """Write an owner-only credentials file through a temporary sibling."""
    credentials_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = credentials_file.with_name(f".{credentials_file.name}.tmp")
    payload = {
        "accounts": [
            {"username": account.username, "password_hash": account.password_hash}
            for account in accounts
        ]
    }
    temporary_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    temporary_file.chmod(CREDENTIALS_FILE_PERMISSION_MODE)
    temporary_file.replace(credentials_file)
    credentials_file.chmod(CREDENTIALS_FILE_PERMISSION_MODE)


def _revoke_existing_sessions(data_directory: Path) -> None:
    """Remove remembered sessions after the login settings change."""
    (data_directory / SESSION_STATE_FILENAME).unlink(missing_ok=True)


def _reuse_or_hash(
    configured_accounts: list[tuple[str, str]],
    stored_accounts: list[StoredAccount],
) -> tuple[list[StoredAccount], bool]:
    """Match the configured accounts against what is already stored.

    Hashing is deliberately slow, so an account whose stored hash still
    verifies against its configured password keeps that hash instead of paying
    for a new one. Verifying the stored hash is also the per-boot self-test.

    Parameters
    ----------
    configured_accounts : list[tuple[str, str]]
        ``(username, plain password)`` pairs read from the settings.
    stored_accounts : list[StoredAccount]
        Accounts currently in ``.ui_credentials.json``.

    Returns
    -------
    tuple[list[StoredAccount], bool]
        The accounts to store, and whether they match what is already stored
        exactly, name for name and hash for hash, in the same order. ``True``
        means the file needs no rewrite and no session has to be dropped.
    """
    stored_hash_for_username = {
        account.username: account.password_hash for account in stored_accounts
    }
    accounts: list[StoredAccount] = []
    every_account_reused = True
    for username, password in configured_accounts:
        stored_hash = stored_hash_for_username.get(username, "")
        if stored_hash and verify_password(password, stored_hash):
            accounts.append(StoredAccount(username, stored_hash))
            continue
        every_account_reused = False
        accounts.append(StoredAccount(username, hash_password(password)))

    # A removed account still sits in the file until it is rewritten, so the
    # counts must agree as well before the file can be left alone.
    unchanged = every_account_reused and len(accounts) == len(stored_accounts)
    return accounts, unchanged


def sync_ui_credentials(data_directory: Path) -> str:
    """Synchronize credentials under one cross-process startup lock.

    Parameters
    ----------
    data_directory : Path
        Directory holding the credentials, session, and lock files.

    Returns
    -------
    str
        Status line describing the verified or newly hashed accounts.
    """
    credentials_file = data_directory / CREDENTIALS_FILENAME
    lock_file = credentials_file.with_name(f"{credentials_file.name}.lock")
    with locked_text_file(lock_file, "a+", fcntl.LOCK_EX):
        return _sync_ui_credentials_unlocked(data_directory)


def _sync_ui_credentials_unlocked(data_directory: Path) -> str:
    """Refresh ``.ui_credentials.json`` from the environment and self-test it.

    Reads up to :data:`MAX_ACCOUNTS` account slots from the process
    environment, which a caller normally fills from ``.env`` in the data
    directory. Accounts whose stored hash already matches their password are
    left as they are, and that check doubles as the per-boot self-test.
    Otherwise the file is rewritten, remembered sessions are dropped so a
    removed or changed account cannot stay signed in, and every new hash is
    verified before success is reported.

    Parameters
    ----------
    data_directory : Path
        Directory holding ``.env`` and ``.ui_credentials.json``.

    Returns
    -------
    str
        One status line for the startup log. Missing settings produce a
        warning line instead of an exception, so the server still starts with
        sign-in unconfigured and every protected route closed.

    Raises
    ------
    RuntimeError
        If a freshly written hash fails verification. That indicates a bug in
        this module, never an operator mistake.
    """
    credentials_file = data_directory / CREDENTIALS_FILENAME
    configured_accounts, complaints = read_configured_accounts()
    complaint_text = "".join(f" WARNING: {complaint}" for complaint in complaints)

    if not configured_accounts:
        credentials_file.unlink(missing_ok=True)
        _revoke_existing_sessions(data_directory)
        return (
            f"{ENV_USERNAME_KEY} or {ENV_PASSWORD_KEY} is not set; browser and "
            f"API access stay closed until both are set in "
            f"{data_directory / DOTENV_FILENAME} and the server restarts."
            f"{complaint_text}"
        )

    if any(password == EXAMPLE_PASSWORD for _, password in configured_accounts):
        complaint_text += (
            f" WARNING: a password is still the example value "
            f"'{EXAMPLE_PASSWORD}'; change it."
        )

    accounts, unchanged = _reuse_or_hash(
        configured_accounts,
        load_ui_accounts(credentials_file),
    )
    account_names = ", ".join(f"'{account.username}'" for account in accounts)

    if unchanged:
        return (
            f"Sign-in credentials for {account_names} verified against "
            f"{credentials_file}.{complaint_text}"
        )

    _write_credentials(credentials_file, accounts)
    _revoke_existing_sessions(data_directory)

    # Self-test: read back what was written and prove every hash verifies.
    written_accounts = load_ui_accounts(credentials_file)
    written_hash_for_username = {
        account.username: account.password_hash for account in written_accounts
    }
    for username, password in configured_accounts:
        written_hash = written_hash_for_username.get(username, "")
        if not written_hash or not verify_password(password, written_hash):
            raise RuntimeError(
                f"Credential self-test failed after writing {credentials_file}."
            )

    return (
        f"Hashed the sign-in passwords for {account_names} into "
        f"{credentials_file} and passed the hash self-test.{complaint_text}"
    )
