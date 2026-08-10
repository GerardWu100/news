"""Request-security helpers for browser-facing responses.

Three questions are answered here: which response headers to send, which
address to charge a failed login to, and whether the request reached the
server over HTTPS.

Content Security Policy
-----------------------
A Content Security Policy (CSP) is a response header that tells the browser
which resources a page may load. Anything the policy does not list is blocked,
so a script injected into the page has nothing to run from. Two policies are
needed because the two HTML pages load different things:

Login page and data responses
    Nothing at all. ``default-src 'none'`` blocks every resource type, and the
    inline stylesheet on the login page is the single exception.
Search page
    Its own scripts and stylesheet, plus the web font files it links to.

Strict Transport Security
-------------------------
``Strict-Transport-Security`` tells a browser to reach this site only over
HTTPS for the stated period. It is sent only on connections that already
arrived over HTTPS, because promising HTTPS over a plain connection can lock a
local deployment out of its own server.
"""

from __future__ import annotations

import json
from ipaddress import ip_address

from fastapi import Request

# One year, the shortest period preload lists accept.
STRICT_TRANSPORT_SECURITY_VALUE = "max-age=31536000; includeSubDomains"

# Hosts the search page loads its web fonts from.
FONT_STYLESHEET_HOST = "https://fonts.googleapis.com"
FONT_FILE_HOST = "https://fonts.gstatic.com"

_SHARED_POLICY_DIRECTIVES = (
    "default-src 'none'",
    "img-src 'self' data:",
    "connect-src 'self'",
    "form-action 'self'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
)

# The login page carries its stylesheet inline, so inline styles are allowed
# there and scripts are not; the page has no script tag of its own.
_LOGIN_PAGE_POLICY = (*_SHARED_POLICY_DIRECTIVES, "style-src 'unsafe-inline'")

# The search page loads package-owned scripts and styles plus the web fonts.
_SEARCH_PAGE_POLICY = (
    *_SHARED_POLICY_DIRECTIVES,
    "script-src 'self'",
    f"style-src 'self' {FONT_STYLESHEET_HOST}",
    f"font-src {FONT_FILE_HOST}",
)

# JSON, CSV, and redirect responses need no resources at all.
_DATA_RESPONSE_POLICY = _SHARED_POLICY_DIRECTIVES

_BASE_HEADERS = {
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


def login_page_headers(*, connection_is_secure: bool = False) -> dict[str, str]:
    """Return response headers for the sign-in page."""
    return _build_headers(_LOGIN_PAGE_POLICY, connection_is_secure)


def search_page_headers(*, connection_is_secure: bool = False) -> dict[str, str]:
    """Return response headers for the browser search page."""
    return _build_headers(_SEARCH_PAGE_POLICY, connection_is_secure)


def data_response_headers(*, connection_is_secure: bool = False) -> dict[str, str]:
    """Return response headers for search results, exports, and redirects."""
    return _build_headers(_DATA_RESPONSE_POLICY, connection_is_secure)


def static_asset_headers(*, connection_is_secure: bool = False) -> dict[str, str]:
    """Return response headers for the package-owned browser files.

    These files hold no account data and no search results, so they stay
    cacheable. Only the content-type and framing protections apply.
    """
    headers = dict(_BASE_HEADERS)
    if connection_is_secure:
        headers["Strict-Transport-Security"] = STRICT_TRANSPORT_SECURITY_VALUE
    return headers


def _build_headers(
    policy_directives: tuple[str, ...],
    connection_is_secure: bool,
) -> dict[str, str]:
    """Combine the shared headers, one policy, and the optional HTTPS promise.

    Parameters
    ----------
    policy_directives : tuple[str, ...]
        Content Security Policy directives for this kind of response.
    connection_is_secure : bool
        Whether the browser reached the server over HTTPS. Only then is
        ``Strict-Transport-Security`` sent.

    Returns
    -------
    dict[str, str]
        Header names and values to attach to the response.
    """
    headers = {
        **_BASE_HEADERS,
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Content-Security-Policy": "; ".join(policy_directives),
    }
    if connection_is_secure:
        headers["Strict-Transport-Security"] = STRICT_TRANSPORT_SECURITY_VALUE
    return headers


def forwarded_headers_are_trustworthy(
    request: Request,
    trust_forwarded_headers: bool,
) -> bool:
    """Return whether this request's proxy headers may be believed.

    Any client can put any value in ``X-Forwarded-For``, so believing it from
    a direct connection would let one caller spend another caller's
    failed-login budget, or claim the connection was encrypted when it was
    not. The setting alone is therefore not enough: the machine that actually
    opened the connection must also be a reverse proxy on the loopback
    interface or a private network, which is where a proxy in front of this
    server lives. A caller arriving straight from a public address is never
    believed, even while the setting is on.

    Parameters
    ----------
    request : Request
        Current request.
    trust_forwarded_headers : bool
        Operator setting from ``[security]`` in the configuration file.

    Returns
    -------
    bool
        ``True`` only when the setting is on and the direct peer is local or
        private.
    """
    if not trust_forwarded_headers:
        return False

    request_client = getattr(request, "client", None)
    peer_address = getattr(request_client, "host", "") if request_client else ""
    if not peer_address:
        return False
    try:
        parsed_address = ip_address(peer_address)
    except ValueError:
        return False
    return (
        parsed_address.is_loopback
        or parsed_address.is_private
        or parsed_address.is_link_local
    )


def client_ip(request: Request, trust_forwarded_headers: bool) -> str:
    """Return the client address that failed-login limits are counted against.

    Parameters
    ----------
    request : Request
        Current request.
    trust_forwarded_headers : bool
        Whether proxy headers may be believed. They are used only when
        :func:`forwarded_headers_are_trustworthy` also agrees.

    Returns
    -------
    str
        Client address, or ``"unknown"`` when no address is available.
    """
    headers = getattr(request, "headers", {})
    if forwarded_headers_are_trustworthy(request, trust_forwarded_headers):
        # Cloudflare puts the original client address in this header.
        cloudflare_ip = headers.get("CF-Connecting-IP")
        if cloudflare_ip:
            return cloudflare_ip.strip()

        # Other proxies put the original address first in this list.
        forwarded_for = headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

    request_client = getattr(request, "client", None)
    if request_client and getattr(request_client, "host", None):
        return str(request_client.host)
    return "unknown"


def request_is_secure(request: Request, trust_forwarded_headers: bool) -> bool:
    """Return whether the request arrived over HTTPS.

    The result decides whether the session cookie carries the ``Secure`` flag,
    which stops a browser from sending it over plain HTTP.

    Parameters
    ----------
    request : Request
        Current request.
    trust_forwarded_headers : bool
        Whether proxy headers may be believed. A proxy that terminates HTTPS
        forwards plain HTTP to this server, so without these headers a
        correctly served page would look insecure. They are used only when
        :func:`forwarded_headers_are_trustworthy` also agrees.

    Returns
    -------
    bool
        ``True`` when the browser connection used HTTPS.
    """
    if request.url.scheme == "https":
        return True
    if not forwarded_headers_are_trustworthy(request, trust_forwarded_headers):
        return False

    headers = getattr(request, "headers", {})
    forwarded_protocol = headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
    if forwarded_protocol.lower() == "https":
        return True

    cloudflare_visitor = headers.get("CF-Visitor", "")
    if not cloudflare_visitor:
        return False
    try:
        visitor_data = json.loads(cloudflare_visitor)
    except json.JSONDecodeError:
        return False
    return (
        isinstance(visitor_data, dict)
        and str(visitor_data.get("scheme", "")).lower() == "https"
    )
