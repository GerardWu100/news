"""Save browser sign-in state in locked, safely replaced JSON files.

Three files live in the data directory:

``.ui_sessions.json``
    ``{"<session id>": {"created_at": <unix seconds>}}``. The session id is the
    random value held by the browser cookie. Nothing else is stored, so the
    file reveals no account details.
``.login_state.json``
    ``{"<client address>": {"failed": <int>, "last_failed": <unix seconds>,
    "banned_until": <unix seconds>}}``. This drives the failed-login limit.
``.login_form_tokens.json``
    One-time sign-in form tokens and their creation times. Atomic consumption
    lets a form page and its submission reach different worker processes.

Every write goes to a temporary sibling file that is then renamed over the
target. A rename is one step for readers, so a reader sees either the old file
or the new one and never a partial file.
"""

from __future__ import annotations

import fcntl
import json
import math
import time
from collections.abc import Callable
from pathlib import Path

from news.web.file_locks import locked_text_file
from news.web.paths import FORM_TOKEN_STATE_FILENAME

type JsonScalar = float | int | str
type JsonRecord = dict[str, JsonScalar]
type JsonState = dict[str, JsonRecord]

AUTH_STATE_FILE_PERMISSION_MODE = 0o600


class AuthStore:
    """Read and replace the session and failed-login files.

    Parameters
    ----------
    session_file : Path
        JSON file mapping session identifiers to creation times.
    login_state_file : Path
        JSON file mapping client addresses to failed-login counters.
    """

    def __init__(self, session_file: Path, login_state_file: Path) -> None:
        self.session_file = session_file
        self.login_state_file = login_state_file
        self.form_token_file = login_state_file.with_name(FORM_TOKEN_STATE_FILENAME)
        for state_file in (session_file, login_state_file, self.form_token_file):
            if state_file.exists():
                state_file.chmod(AUTH_STATE_FILE_PERMISSION_MODE)

    @staticmethod
    def _lock_file(state_file: Path) -> Path:
        """Return the stable lock path beside one replaceable state file."""
        return state_file.with_name(f"{state_file.name}.lock")

    @staticmethod
    def _read_unlocked(state_file: Path) -> JsonState:
        """Read one JSON mapping, treating absent or invalid content as empty."""
        if not state_file.exists():
            return {}
        try:
            raw_state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(raw_state, dict):
            return {}

        # Keep only the record shape the session and limit code expects.
        # Dropping malformed entries preserves the healthy ones.
        return {
            str(key): value
            for key, value in raw_state.items()
            if isinstance(value, dict)
        }

    @staticmethod
    def _write_unlocked(state_file: Path, state: JsonState) -> None:
        """Write one state file through a temporary sibling, then rename it."""
        state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = state_file.with_name(f".{state_file.name}.tmp")
        temporary_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary_file.chmod(AUTH_STATE_FILE_PERMISSION_MODE)
        temporary_file.replace(state_file)
        state_file.chmod(AUTH_STATE_FILE_PERMISSION_MODE)

    def _read(self, state_file: Path) -> JsonState:
        """Read state while holding a shared lock."""
        with locked_text_file(self._lock_file(state_file), "a+", fcntl.LOCK_SH):
            return self._read_unlocked(state_file)

    def _write(self, state_file: Path, state: JsonState) -> None:
        """Replace state while holding an exclusive lock."""
        with locked_text_file(self._lock_file(state_file), "a+", fcntl.LOCK_EX):
            self._write_unlocked(state_file, state)

    def update_login_state(self, update: Callable[[JsonState], None]) -> JsonState:
        """Apply one read-modify-write transaction to the failed-login file.

        Parameters
        ----------
        update : Callable[[JsonState], None]
            Function that edits the state mapping in place.

        Returns
        -------
        JsonState
            The mapping as written, so the caller can inspect the new counters
            without a second read.
        """
        with locked_text_file(
            self._lock_file(self.login_state_file),
            "a+",
            fcntl.LOCK_EX,
        ):
            state = self._read_unlocked(self.login_state_file)
            update(state)
            self._write_unlocked(self.login_state_file, state)
            return state

    def load_login_state(self) -> JsonState:
        """Return the current failed-login counters for every client address."""
        return self._read(self.login_state_file)

    def update_form_tokens(self, update: Callable[[JsonState], None]) -> JsonState:
        """Apply one atomic update to cross-worker sign-in form tokens.

        Parameters
        ----------
        update : Callable[[JsonState], None]
            Function that edits the token mapping while the exclusive file
            lock is held.

        Returns
        -------
        JsonState
            Token mapping exactly as written.
        """
        with locked_text_file(
            self._lock_file(self.form_token_file),
            "a+",
            fcntl.LOCK_EX,
        ):
            state = self._read_unlocked(self.form_token_file)
            update(state)
            self._write_unlocked(self.form_token_file, state)
            return state

    def update_sessions(
        self,
        update: Callable[[JsonState], None],
        max_age_seconds: int,
    ) -> JsonState:
        """Apply one read-modify-write transaction to the session file.

        The read, the change, and the write happen under a single exclusive
        lock, so two processes signing in at the same moment cannot overwrite
        each other's session.

        Parameters
        ----------
        update : Callable[[JsonState], None]
            Function that edits the session mapping in place.
        max_age_seconds : int
            Session lifetime. Expired records are dropped before ``update``
            runs, so a caller never sees one.

        Returns
        -------
        JsonState
            The mapping as written.
        """
        with locked_text_file(
            self._lock_file(self.session_file),
            "a+",
            fcntl.LOCK_EX,
        ):
            state = _live_sessions(
                self._read_unlocked(self.session_file),
                max_age_seconds,
            )
            update(state)
            self._write_unlocked(self.session_file, state)
            return state

    def load_sessions(self, max_age_seconds: int) -> JsonState:
        """Return well-formed sessions that have not expired.

        Parameters
        ----------
        max_age_seconds : int
            Session lifetime. Records older than this, and records with a
            creation time in the future or one that is not a finite number,
            are dropped.

        Returns
        -------
        JsonState
            Mapping of session identifier to its stored fields.
        """
        return _live_sessions(self._read(self.session_file), max_age_seconds)

    def save_sessions(self, sessions: JsonState) -> None:
        """Replace the remembered sessions in one step."""
        self._write(self.session_file, sessions)


def _live_sessions(raw_sessions: JsonState, max_age_seconds: int) -> JsonState:
    """Return the sessions that are well formed and have not expired.

    Parameters
    ----------
    raw_sessions : JsonState
        Sessions exactly as read from the file.
    max_age_seconds : int
        Session lifetime. Records older than this, records created in the
        future, and records whose creation time is not a finite number are
        dropped.

    Returns
    -------
    JsonState
        Surviving sessions with their stored fields preserved, so a sign-out
        token saved beside the creation time is not lost on the next write.
    """
    current_time = time.time()
    valid_sessions: JsonState = {}
    for session_id, session in raw_sessions.items():
        try:
            created_at = float(session.get("created_at", 0))
        except (TypeError, ValueError):
            continue
        session_age_seconds = current_time - created_at
        if math.isfinite(created_at) and 0 <= session_age_seconds <= max_age_seconds:
            valid_sessions[session_id] = {**session, "created_at": created_at}
    return valid_sessions
