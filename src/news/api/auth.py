"""Sign-in state, sign-in routes, and the check that guards every API route.

Two ways to prove who you are are supported, and both check the same set of
accounts. The operator may configure up to three accounts (see
:mod:`news.web.credentials`); any of them opens every route, so the accounts
separate people, not permissions.

Session cookie
    A browser posts the sign-in form once. The server stores a random session
    identifier together with the account name that signed in, and hands the
    identifier back as a cookie.
HTTP Basic
    A program, in practice the ``news-search`` command, puts an account name
    and password in an ``Authorization`` header on every request.

Protection against guessing
---------------------------
Passwords are stored only as PBKDF2 hashes, and failed attempts are counted
per client address. After ``MAX_FAILED_ATTEMPTS`` failures inside
``FAILURE_WINDOW_SECONDS`` the address is refused for ``BAN_SECONDS``.

Protection against unwanted form submissions
--------------------------------------------
Cross-Site Request Forgery (CSRF) is when another site makes a signed-in
browser submit a form to this server. Every form here carries a random token
that the server issued and remembers, and a form arriving without the matching
token is rejected. The sign-in form uses a one-time token; the sign-out button
uses a token tied to the session.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import math
import secrets
import threading
import time
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response

from news.api.login_page import render_login_page
from news.web.auth_store import AuthStore, JsonRecord, JsonState
from news.web.credentials import load_ui_accounts
from news.web.passwords import verify_password
from news.web.security import client_ip, login_page_headers, request_is_secure

SESSION_COOKIE_NAME = "news_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
FORM_TOKEN_TTL_SECONDS = 10 * 60
MAX_FAILED_ATTEMPTS = 5
FAILURE_WINDOW_SECONDS = 10 * 60
BAN_SECONDS = 15 * 60
# A record is useless once its window has passed and its ban has expired.
# Without this, the failed-login file would keep one row per address forever,
# and every failed attempt rewrites the whole file.
FAILURE_RECORD_LIFETIME_SECONDS = FAILURE_WINDOW_SECONDS + BAN_SECONDS
# An unauthenticated caller can request sign-in forms in a loop, so the number
# of unreturned tokens held in memory is capped. The oldest are dropped first;
# a caller whose token is dropped simply reloads the form.
MAX_PENDING_FORM_TOKENS = 2048
# Hashing a password takes about a third of a second on purpose, so a command
# line that pages through results is not made to pay that on every request.
BASIC_CREDENTIAL_CACHE_SECONDS = 300
# Submissions longer than this are refused before any hashing work is done.
MAX_CREDENTIAL_LENGTH = 1000

LOGIN_PATH = "/login"
LOGOUT_PATH = "/logout"
SESSION_INFO_PATH = "/api/session"

_MESSAGE_FOR_REASON: dict[str, str] = {
    "expired_form": "Your sign-in form expired. Try again.",
    "banned": "Too many failed attempts. Try again later.",
    "bad_credentials": "Invalid username or password.",
    "unconfigured": (
        "Sign-in is not configured. Set UI_USERNAME and UI_PASSWORD, "
        "then restart the server."
    ),
    "bad_request": "Invalid request.",
    "signed_out": "You are signed out.",
}


class LoginSessions:
    """Hold sign-in state for one running application.

    Sessions and failed-login counters live in files, and every read and write
    goes through the locked store rather than through a copy held in memory.
    That costs one small file read per signed-in request and buys correctness
    when more than one process serves the application: a browser that signs in
    through one worker is recognized by all of them. One-time form tokens use
    the same locked store, while the password-hash cache remains per process.

    Parameters
    ----------
    auth_store : AuthStore
        Reader and writer for the session and failed-login files.
    credentials_file : Path
        Path to ``.ui_credentials.json``.
    trust_forwarded_headers : bool
        Whether proxy headers may be believed when reading the client address
        and the HTTPS state of the connection.
    """

    def __init__(
        self,
        auth_store: AuthStore,
        *,
        credentials_file: Path,
        trust_forwarded_headers: bool,
    ) -> None:
        self.auth_store = auth_store
        self.credentials_file = credentials_file
        self.trust_forwarded_headers = trust_forwarded_headers
        self._lock = threading.RLock()
        # digest of an accepted Authorization header -> expiry time
        self._accepted_basic_headers: dict[str, float] = {}
        # Modification time of the account file the cache above was filled
        # under. A different value means the password changed.
        self._cached_credentials_changed_at = self.credentials_changed_at()

    def login_is_configured(self) -> bool:
        """Return whether at least one stored account exists."""
        return bool(load_ui_accounts(self.credentials_file))

    def credentials_changed_at(self) -> float:
        """Return when the stored accounts were last written, or zero.

        Reading the file's modification time is how a running process notices
        that the operator changed the password, so a header accepted under the
        old one stops being accepted.
        """
        try:
            return self.credentials_file.stat().st_mtime
        except OSError:
            return 0.0

    def client_address(self, request: Request) -> str:
        """Return the address that failed attempts are counted against."""
        return client_ip(request, self.trust_forwarded_headers)

    def connection_is_secure(self, request: Request) -> bool:
        """Return whether the browser reached the server over HTTPS."""
        return request_is_secure(request, self.trust_forwarded_headers)

    def ban_seconds_remaining(self, address: str) -> int:
        """Return how many seconds this address stays refused, or zero."""
        return _ban_seconds_remaining(self.auth_store.load_login_state(), address)

    def record_failure(self, address: str) -> int:
        """Count one failed attempt and return the resulting ban in seconds.

        Parameters
        ----------
        address : str
            Client address responsible for the failed attempt.

        Returns
        -------
        int
            Seconds the address is now refused for, or zero when it is still
            below the failure limit.
        """
        updated_state = self.auth_store.update_login_state(
            lambda state: _add_failure(state, address)
        )
        return _ban_seconds_remaining(updated_state, address)

    def clear_failures(self, address: str) -> None:
        """Reset the failure counters for one address after a success."""
        self.auth_store.update_login_state(
            lambda state: _reset_failures(state, address)
        )

    def matching_account(self, username: str, password: str) -> str | None:
        """Return the stored account name this pair signs in as, or ``None``.

        The submitted name is compared against every stored account. Exactly
        one password hash is then checked, either the matched account's or,
        when no name matched, the first account's as a decoy. Doing the hashing
        work either way keeps a wrong account name as expensive as a wrong
        password, so the timing does not reveal which half was wrong.

        Parameters
        ----------
        username : str
            Account name submitted by a browser form or a Basic header.
        password : str
            Password submitted with it.

        Returns
        -------
        str | None
            The stored account name on success, otherwise ``None``.
        """
        if (
            len(username) > MAX_CREDENTIAL_LENGTH
            or len(password) > MAX_CREDENTIAL_LENGTH
        ):
            return None
        accounts = load_ui_accounts(self.credentials_file)
        if not accounts:
            return None

        matched_account = None
        for account in accounts:
            if secrets.compare_digest(
                username.encode("utf-8"),
                account.username.encode("utf-8"),
            ):
                matched_account = account
                break

        hash_to_check = (
            matched_account.password_hash
            if matched_account is not None
            else accounts[0].password_hash
        )
        password_matches = verify_password(password, hash_to_check)
        if matched_account is None or not password_matches:
            return None
        return matched_account.username

    def issue_form_token(self) -> tuple[str, str]:
        """Create a one-time sign-in form token.

        Returns
        -------
        tuple[str, str]
            ``(token_id, token)``. The page carries both; the server keeps the
            token under the identifier until the form comes back or expires.
        """
        token_id = secrets.token_urlsafe(16)
        token = secrets.token_urlsafe(32)
        issued_at = time.time()

        def add_token(form_tokens: JsonState) -> None:
            """Drop expired rows, add the token, and enforce the shared cap."""
            _drop_expired_form_tokens(form_tokens, now=issued_at)
            form_tokens[token_id] = {"token": token, "created_at": issued_at}
            while len(form_tokens) > MAX_PENDING_FORM_TOKENS:
                oldest_token_id = min(
                    form_tokens,
                    key=lambda stored_id: float(
                        form_tokens[stored_id].get("created_at", 0) or 0
                    ),
                )
                form_tokens.pop(oldest_token_id, None)

        self.auth_store.update_form_tokens(add_token)
        return token_id, token

    def consume_form_token(self, token_id: str, token: str) -> bool:
        """Check a returned form token and remove it so it cannot be reused."""
        consumed: dict[str, JsonRecord] = {}
        current_time = time.time()

        def consume_token(form_tokens: JsonState) -> None:
            """Remove the submitted token while holding the cross-worker lock."""
            _drop_expired_form_tokens(form_tokens, now=current_time)
            stored_token = form_tokens.pop(token_id, None)
            if stored_token is not None:
                consumed["token"] = stored_token

        self.auth_store.update_form_tokens(consume_token)
        stored_token = consumed.get("token")
        if stored_token is None:
            return False
        expected_token = str(stored_token.get("token", ""))
        issued_at = float(stored_token.get("created_at", 0) or 0)
        if current_time - issued_at > FORM_TOKEN_TTL_SECONDS:
            return False
        return bool(expected_token) and secrets.compare_digest(token, expected_token)

    def start_session(self, username: str) -> str:
        """Create a session and return the identifier for the cookie.

        Parameters
        ----------
        username : str
            Stored account name that just signed in. It is kept in the session
            record so any worker process can name the signed-in account
            without asking for the password again.

        Returns
        -------
        str
            Session identifier to place in the cookie.
        """
        session_id = secrets.token_urlsafe(32)

        def add_session(sessions: JsonState) -> None:
            """Record the new session beside the ones already stored."""
            sessions[session_id] = {"created_at": time.time(), "username": username}

        self.auth_store.update_sessions(add_session, SESSION_MAX_AGE_SECONDS)
        return session_id

    def end_session(self, session_id: str | None) -> None:
        """Forget one session, and with it its sign-out token."""
        if not session_id:
            return

        def remove_session(sessions: JsonState) -> None:
            """Drop the signed-out session from the stored mapping."""
            sessions.pop(session_id, None)

        self.auth_store.update_sessions(remove_session, SESSION_MAX_AGE_SECONDS)

    def session_is_valid(self, request: Request) -> bool:
        """Return whether the request carries a live session cookie."""
        return self._stored_session(request) is not None

    def session_username(self, request: Request) -> str:
        """Return the account name this request is signed in as.

        Returns
        -------
        str
            The account name stored with the session, or an empty string when
            the request carries no live session.
        """
        session = self._stored_session(request)
        if session is None:
            return ""
        return str(session.get("username", ""))

    def sign_out_token(self, request: Request) -> str:
        """Return this session's sign-out token, creating it when needed.

        The token is kept in the session record rather than in memory, so a
        sign-out form built by one process is accepted by any process.
        """
        session_id = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not session_id:
            return ""

        issued_token = secrets.token_urlsafe(32)
        stored_tokens: dict[str, str] = {}

        def read_or_add_token(sessions: JsonState) -> None:
            """Reuse this session's token, or store a freshly made one."""
            session = sessions.get(session_id)
            if session is None:
                return
            existing_token = str(session.get("sign_out_token", ""))
            if existing_token:
                stored_tokens["token"] = existing_token
                return
            session["sign_out_token"] = issued_token
            stored_tokens["token"] = issued_token

        self.auth_store.update_sessions(read_or_add_token, SESSION_MAX_AGE_SECONDS)
        return stored_tokens.get("token", "")

    def sign_out_token_is_valid(self, request: Request, token: str) -> bool:
        """Check a submitted sign-out token against the stored one."""
        session = self._stored_session(request)
        if session is None:
            return False
        expected_token = str(session.get("sign_out_token", ""))
        if not expected_token:
            return False
        return secrets.compare_digest(token, expected_token)

    def _stored_session(self, request: Request) -> JsonRecord | None:
        """Return the stored record for this request's cookie, if it is live.

        Parameters
        ----------
        request : Request
            Current request, whose cookie names the session.

        Returns
        -------
        JsonRecord | None
            The session's stored fields, or ``None`` when the cookie is
            missing, unknown, or expired.
        """
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if not session_id:
            return None
        sessions = self.auth_store.load_sessions(SESSION_MAX_AGE_SECONDS)
        return sessions.get(session_id)

    def basic_header_is_valid(self, authorization_header: str) -> bool:
        """Check an HTTP Basic ``Authorization`` header.

        A header that verifies is remembered by digest for
        ``BASIC_CREDENTIAL_CACHE_SECONDS`` so a run of command-line requests
        does not repeat the deliberately slow password hashing every time. Only
        the digest is kept, never the password. Writing a new account file
        empties the cache, so a header accepted under the old password stops
        working immediately rather than at the end of its remaining time.

        Parameters
        ----------
        authorization_header : str
            Raw header value, expected to look like ``Basic <base64>``.

        Returns
        -------
        bool
            ``True`` when the header carries a configured account name and its
            password.
        """
        scheme, _, encoded_credentials = authorization_header.partition(" ")
        if scheme.lower() != "basic" or not encoded_credentials:
            return False

        header_digest = hashlib.sha256(authorization_header.encode("utf-8")).hexdigest()
        now = time.time()
        credentials_written_at = self.credentials_changed_at()
        with self._lock:
            if credentials_written_at != self._cached_credentials_changed_at:
                self._accepted_basic_headers.clear()
                self._cached_credentials_changed_at = credentials_written_at
            self._accepted_basic_headers = {
                digest: expires_at
                for digest, expires_at in self._accepted_basic_headers.items()
                if expires_at > now
            }
            if header_digest in self._accepted_basic_headers:
                return True

        try:
            decoded_credentials = base64.b64decode(
                encoded_credentials,
                validate=True,
            ).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return False
        username, separator, password = decoded_credentials.partition(":")
        if not separator:
            return False

        if self.matching_account(username, password) is None:
            return False
        with self._lock:
            self._accepted_basic_headers[header_digest] = (
                time.time() + BASIC_CREDENTIAL_CACHE_SECONDS
            )
        return True

    def forget_accepted_basic_headers(self) -> None:
        """Drop remembered Basic headers, for example after a password change."""
        with self._lock:
            self._accepted_basic_headers.clear()


def request_is_signed_in(request: Request) -> bool:
    """Return whether a request proves the account by cookie or by header.

    Parameters
    ----------
    request : Request
        Current request. Its application must carry a
        :class:`LoginSessions` on ``app.state.login_sessions``.

    Returns
    -------
    bool
        ``True`` when a live session cookie or valid HTTP Basic header is
        present. Always ``False`` while sign-in is unconfigured, so a server
        without credentials serves nothing rather than everything.
    """
    sessions: LoginSessions = request.app.state.login_sessions
    if not sessions.login_is_configured():
        return False
    if sessions.session_is_valid(request):
        return True

    authorization_header = request.headers.get("Authorization", "")
    if not authorization_header:
        return False

    # Count a wrong header the same way a wrong form submission is counted, so
    # the failure limit cannot be sidestepped by guessing through this path.
    address = sessions.client_address(request)
    if sessions.ban_seconds_remaining(address) > 0:
        return False
    if sessions.basic_header_is_valid(authorization_header):
        sessions.clear_failures(address)
        return True
    sessions.record_failure(address)
    return False


def _drop_expired_form_tokens(form_tokens: JsonState, *, now: float) -> None:
    """Remove expired or malformed one-time form tokens in place.

    Parameters
    ----------
    form_tokens : JsonState
        Mutable token identifier to token-details mapping.
    now : float
        Current Unix time used for one consistent expiry decision.
    """
    cutoff = now - FORM_TOKEN_TTL_SECONDS
    for token_id, token_data in list(form_tokens.items()):
        try:
            created_at = float(token_data.get("created_at", 0) or 0)
        except (TypeError, ValueError):
            created_at = 0.0
        if not math.isfinite(created_at) or created_at < cutoff or created_at > now:
            form_tokens.pop(token_id, None)


def require_signed_in(request: Request) -> None:
    """Reject an API request that does not prove the account.

    Used as a FastAPI dependency. The 401 response deliberately omits the
    ``WWW-Authenticate`` header: the browser client handles the status itself
    and would otherwise show a second, native password box on top of its own
    sign-in page. The command line sends its header without waiting to be
    asked, so nothing is lost.

    Raises
    ------
    HTTPException
        401 when the request is not signed in.
    """
    if request_is_signed_in(request):
        return
    sessions: LoginSessions = request.app.state.login_sessions
    if not sessions.login_is_configured():
        raise HTTPException(
            status_code=401,
            detail=_MESSAGE_FOR_REASON["unconfigured"],
        )
    raise HTTPException(status_code=401, detail="Sign in to use this endpoint.")


def build_auth_router() -> APIRouter:
    """Build the router holding the sign-in, sign-out, and session routes."""
    router = APIRouter()

    @router.get(LOGIN_PATH, include_in_schema=False)
    async def login_form(request: Request, reason: str = "") -> Response:
        """Show the sign-in form, or send a signed-in browser to the app."""
        sessions: LoginSessions = request.app.state.login_sessions
        if sessions.session_is_valid(request):
            return RedirectResponse(url="/", status_code=302)

        message = _MESSAGE_FOR_REASON.get(reason, "")
        remaining_ban = sessions.ban_seconds_remaining(sessions.client_address(request))
        if remaining_ban > 0:
            message = f"Too many failed attempts. Try again in {remaining_ban} seconds."
        elif not sessions.login_is_configured():
            message = _MESSAGE_FOR_REASON["unconfigured"]

        token_id, token = sessions.issue_form_token()
        return render_login_page(
            message=message,
            form_token=token,
            form_token_id=token_id,
            headers=login_page_headers(
                connection_is_secure=sessions.connection_is_secure(request)
            ),
        )

    @router.post(LOGIN_PATH, include_in_schema=False)
    async def sign_in(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        form_token: str = Form(...),
        form_token_id: str = Form(...),
    ) -> RedirectResponse:
        """Check a submitted account name and password and start a session.

        Parameters
        ----------
        request : Request
            Current request, carrying the client address and cookies.
        username : str
            Account name typed into the form.
        password : str
            Password typed into the form.
        form_token : str
            One-time token issued with the form.
        form_token_id : str
            Identifier the server uses to find its copy of ``form_token``.

        Returns
        -------
        RedirectResponse
            The browser app after a success, or the form with a reason after
            a failure.
        """
        sessions: LoginSessions = request.app.state.login_sessions

        # Check the form token first, before any password work or counter
        # update, so a forged submission cannot spend another user's attempts.
        if not sessions.consume_form_token(form_token_id, form_token):
            return _redirect_to_login("expired_form")

        address = sessions.client_address(request)
        if sessions.ban_seconds_remaining(address) > 0:
            return _redirect_to_login("banned")
        if not sessions.login_is_configured():
            return _redirect_to_login("unconfigured")
        if (
            len(username) > MAX_CREDENTIAL_LENGTH
            or len(password) > MAX_CREDENTIAL_LENGTH
        ):
            return _redirect_to_login("bad_request")

        signed_in_username = sessions.matching_account(username, password)
        if signed_in_username is None:
            if sessions.record_failure(address) > 0:
                return _redirect_to_login("banned")
            return _redirect_to_login("bad_credentials")

        sessions.clear_failures(address)
        session_id = sessions.start_session(signed_in_username)
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_id,
            httponly=True,
            samesite="lax",
            max_age=SESSION_MAX_AGE_SECONDS,
            secure=sessions.connection_is_secure(request),
        )
        return response

    @router.post(LOGOUT_PATH, include_in_schema=False)
    async def sign_out(request: Request, sign_out_token: str = Form(...)) -> Response:
        """End the current session after checking its sign-out token."""
        sessions: LoginSessions = request.app.state.login_sessions
        if not sessions.sign_out_token_is_valid(request, sign_out_token):
            raise HTTPException(status_code=403, detail="Invalid sign-out token.")
        sessions.end_session(request.cookies.get(SESSION_COOKIE_NAME))
        response = _redirect_to_login("signed_out")
        response.delete_cookie(SESSION_COOKIE_NAME)
        return response

    @router.get(SESSION_INFO_PATH, include_in_schema=False)
    async def session_info(request: Request) -> dict[str, str]:
        """Return the signed-in account name and this session's sign-out token."""
        sessions: LoginSessions = request.app.state.login_sessions
        if not sessions.session_is_valid(request):
            raise HTTPException(status_code=401, detail="No browser session.")
        return {
            "username": sessions.session_username(request),
            "sign_out_token": sessions.sign_out_token(request),
        }

    return router


def _redirect_to_login(reason: str) -> RedirectResponse:
    """Send the browser back to the sign-in form with a reason to display."""
    return RedirectResponse(url=f"{LOGIN_PATH}?reason={reason}", status_code=303)


def _ban_seconds_remaining(state: JsonState, address: str) -> int:
    """Return the seconds left on this address's ban, or zero."""
    record = state.get(address, {})
    try:
        banned_until = float(record.get("banned_until", 0))
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(banned_until):
        return 0
    remaining_seconds = banned_until - time.time()
    return int(remaining_seconds) + 1 if remaining_seconds > 0 else 0


def _drop_stale_failure_records(state: JsonState, now: float) -> None:
    """Remove failure records that can no longer affect any decision.

    A record matters only while its address is inside the rolling failure
    window or still banned. Anything older changes nothing, so keeping it only
    grows the file that every failed attempt has to read and rewrite.

    Parameters
    ----------
    state : JsonState
        Failed-login mapping, edited in place.
    now : float
        Current Unix time in seconds.
    """
    stale_addresses = [
        address
        for address, record in state.items()
        if _failure_record_is_stale(record, now)
    ]
    for address in stale_addresses:
        del state[address]


def _failure_record_is_stale(record: JsonRecord, now: float) -> bool:
    """Return whether one failure record has outlived its usefulness."""
    try:
        last_failure_at = float(record.get("last_failed", 0) or 0)
        banned_until = float(record.get("banned_until", 0) or 0)
    except (TypeError, ValueError):
        # A record that cannot be read is a record that cannot be trusted.
        return True
    if not math.isfinite(last_failure_at) or not math.isfinite(banned_until):
        return True
    if banned_until > now:
        return False
    return now - last_failure_at > FAILURE_RECORD_LIFETIME_SECONDS


def _add_failure(state: JsonState, address: str) -> None:
    """Count one failure for an address and set a ban once the limit is hit.

    Parameters
    ----------
    state : JsonState
        Failed-login mapping, edited in place.
    address : str
        Client address responsible for the failed attempt.
    """
    now = time.time()
    # Clear out spent records first, so the file this write produces stays
    # proportional to the addresses that are currently failing.
    _drop_stale_failure_records(state, now)
    record = state.get(address, {})
    try:
        last_failure_at = float(record.get("last_failed", 0))
        failure_count = int(record.get("failed", 0))
    except (TypeError, ValueError):
        last_failure_at = 0.0
        failure_count = 0
    if not math.isfinite(last_failure_at) or failure_count < 0:
        last_failure_at = 0.0
        failure_count = 0

    # A failure outside the rolling window starts a fresh count, so occasional
    # typos spread over hours never add up to a ban.
    if now - last_failure_at > FAILURE_WINDOW_SECONDS:
        failure_count = 0

    failure_count += 1
    record.update({"failed": failure_count, "last_failed": now})
    if failure_count >= MAX_FAILED_ATTEMPTS:
        record["banned_until"] = now + BAN_SECONDS
    state[address] = record


def _reset_failures(state: JsonState, address: str) -> None:
    """Forget one address after a success and drop other spent records.

    Removing the row rather than zeroing it keeps the file free of entries
    that record nothing.
    """
    state.pop(address, None)
    _drop_stale_failure_records(state, time.time())
