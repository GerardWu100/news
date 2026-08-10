"""Sign-in state, sign-in routes, and the check that guards every API route.

Two ways to prove who you are are supported, and both check the same account:

Session cookie
    A browser posts the sign-in form once. The server stores a random session
    identifier and hands the same value back as a cookie.
HTTP Basic
    A program, in practice the ``news-search`` command, puts the account name
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
from news.web.auth_store import AuthStore, JsonState
from news.web.credentials import load_ui_credentials
from news.web.passwords import verify_password
from news.web.security import client_ip, request_is_secure, security_headers

SESSION_COOKIE_NAME = "news_session"
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
FORM_TOKEN_TTL_SECONDS = 10 * 60
MAX_FAILED_ATTEMPTS = 5
FAILURE_WINDOW_SECONDS = 10 * 60
BAN_SECONDS = 15 * 60
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

    Sessions and failed-login counters survive a restart because they are kept
    in files; the in-memory copies here are the fast path. Form tokens are
    memory-only, so a restart simply asks the browser to reload the form.

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
        self._sessions: JsonState = auth_store.load_sessions(SESSION_MAX_AGE_SECONDS)
        # session identifier -> sign-out token
        self._session_tokens: dict[str, str] = {}
        # one-time form token identifier -> {"token": str, "created_at": float}
        self._form_tokens: dict[str, dict[str, float | str]] = {}
        # digest of an accepted Authorization header -> expiry time
        self._accepted_basic_headers: dict[str, float] = {}

    def login_is_configured(self) -> bool:
        """Return whether a stored account name and password hash exist."""
        return load_ui_credentials(self.credentials_file) is not None

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

    def credentials_are_valid(self, username: str, password: str) -> bool:
        """Check one account name and password against the stored hash.

        Both halves are always checked, so a wrong account name costs the same
        time as a wrong password and the response does not reveal which half
        was wrong.
        """
        if (
            len(username) > MAX_CREDENTIAL_LENGTH
            or len(password) > MAX_CREDENTIAL_LENGTH
        ):
            return False
        credentials = load_ui_credentials(self.credentials_file)
        if credentials is None:
            return False
        expected_username, expected_password_hash = credentials
        username_matches = secrets.compare_digest(
            username.encode("utf-8"),
            expected_username.encode("utf-8"),
        )
        password_matches = verify_password(password, expected_password_hash)
        return username_matches and password_matches

    def issue_form_token(self) -> tuple[str, str]:
        """Create a one-time sign-in form token.

        Returns
        -------
        tuple[str, str]
            ``(token_id, token)``. The page carries both; the server keeps the
            token under the identifier until the form comes back or expires.
        """
        with self._lock:
            self._drop_expired_form_tokens()
            token_id = secrets.token_urlsafe(16)
            token = secrets.token_urlsafe(32)
            self._form_tokens[token_id] = {"token": token, "created_at": time.time()}
        return token_id, token

    def consume_form_token(self, token_id: str, token: str) -> bool:
        """Check a returned form token and remove it so it cannot be reused."""
        with self._lock:
            stored_token = self._form_tokens.pop(token_id, None)
        if stored_token is None:
            return False
        expected_token = str(stored_token.get("token", ""))
        issued_at = float(stored_token.get("created_at", 0) or 0)
        if time.time() - issued_at > FORM_TOKEN_TTL_SECONDS:
            return False
        return bool(expected_token) and secrets.compare_digest(token, expected_token)

    def start_session(self) -> str:
        """Create a session and return the identifier for the cookie."""
        session_id = secrets.token_urlsafe(32)
        with self._lock:
            self._drop_expired_sessions()
            self._sessions[session_id] = {"created_at": time.time()}
            self.auth_store.save_sessions(self._sessions)
        return session_id

    def end_session(self, session_id: str | None) -> None:
        """Forget one session and its sign-out token."""
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)
            self._session_tokens.pop(session_id, None)
            self.auth_store.save_sessions(self._sessions)

    def session_is_valid(self, request: Request) -> bool:
        """Return whether the request carries a live session cookie."""
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if not session_id:
            return False
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return False
            if _session_has_expired(session.get("created_at")):
                self._sessions.pop(session_id, None)
                self._session_tokens.pop(session_id, None)
                self.auth_store.save_sessions(self._sessions)
                return False
        return True

    def sign_out_token(self, request: Request) -> str:
        """Return this session's sign-out token, creating it when needed."""
        session_id = request.cookies.get(SESSION_COOKIE_NAME, "")
        if not session_id:
            return ""
        with self._lock:
            token = self._session_tokens.get(session_id, "")
            if not token:
                token = secrets.token_urlsafe(32)
                self._session_tokens[session_id] = token
            return token

    def sign_out_token_is_valid(self, request: Request, token: str) -> bool:
        """Check a submitted sign-out token against the stored one."""
        session_id = request.cookies.get(SESSION_COOKIE_NAME, "")
        with self._lock:
            expected_token = self._session_tokens.get(session_id, "")
        if not expected_token:
            return False
        return secrets.compare_digest(token, expected_token)

    def basic_header_is_valid(self, authorization_header: str) -> bool:
        """Check an HTTP Basic ``Authorization`` header.

        A header that verifies is remembered by digest for
        ``BASIC_CREDENTIAL_CACHE_SECONDS`` so a run of command-line requests
        does not repeat the deliberately slow password hashing every time. Only
        the digest is kept, never the password.

        Parameters
        ----------
        authorization_header : str
            Raw header value, expected to look like ``Basic <base64>``.

        Returns
        -------
        bool
            ``True`` when the header carries the configured account name and
            password.
        """
        scheme, _, encoded_credentials = authorization_header.partition(" ")
        if scheme.lower() != "basic" or not encoded_credentials:
            return False

        header_digest = hashlib.sha256(
            authorization_header.encode("utf-8")
        ).hexdigest()
        now = time.time()
        with self._lock:
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

        if not self.credentials_are_valid(username, password):
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

    def _drop_expired_sessions(self) -> None:
        """Remove expired sessions from memory and from the session file."""
        expired_session_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if _session_has_expired(session.get("created_at"))
        ]
        if not expired_session_ids:
            return
        for session_id in expired_session_ids:
            self._sessions.pop(session_id, None)
            self._session_tokens.pop(session_id, None)
        self.auth_store.save_sessions(self._sessions)

    def _drop_expired_form_tokens(self) -> None:
        """Remove sign-in form tokens that were never returned."""
        cutoff = time.time() - FORM_TOKEN_TTL_SECONDS
        self._form_tokens = {
            token_id: token_data
            for token_id, token_data in self._form_tokens.items()
            if float(token_data.get("created_at", 0) or 0) >= cutoff
        }


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
        remaining_ban = sessions.ban_seconds_remaining(
            sessions.client_address(request)
        )
        if remaining_ban > 0:
            message = (
                f"Too many failed attempts. Try again in {remaining_ban} seconds."
            )
        elif not sessions.login_is_configured():
            message = _MESSAGE_FOR_REASON["unconfigured"]

        token_id, token = sessions.issue_form_token()
        return render_login_page(
            message=message,
            form_token=token,
            form_token_id=token_id,
            headers=security_headers(),
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

        if not sessions.credentials_are_valid(username, password):
            if sessions.record_failure(address) > 0:
                return _redirect_to_login("banned")
            return _redirect_to_login("bad_credentials")

        sessions.clear_failures(address)
        session_id = sessions.start_session()
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
        credentials = load_ui_credentials(sessions.credentials_file)
        return {
            "username": credentials[0] if credentials else "",
            "sign_out_token": sessions.sign_out_token(request),
        }

    return router


def _redirect_to_login(reason: str) -> RedirectResponse:
    """Send the browser back to the sign-in form with a reason to display."""
    return RedirectResponse(url=f"{LOGIN_PATH}?reason={reason}", status_code=303)


def _session_has_expired(created_at_value: float | int | str | None) -> bool:
    """Return whether a stored creation time is missing, odd, or too old."""
    try:
        created_at = float(created_at_value or 0)
    except (TypeError, ValueError):
        return True
    if not math.isfinite(created_at):
        return True
    session_age_seconds = time.time() - created_at
    return not 0 <= session_age_seconds <= SESSION_MAX_AGE_SECONDS


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
    """Clear the failure counters and ban for one address."""
    if address in state:
        state[address] = {"failed": 0, "last_failed": 0, "banned_until": 0}
