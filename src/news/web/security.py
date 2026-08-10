"""Request-security helpers for browser-facing responses.

Three questions are answered here: which response headers to send, which
address to charge a failed login to, and whether the request reached the
server over HTTPS.
"""

from __future__ import annotations

import json

from fastapi import Request


def security_headers(script_nonce: str | None = None) -> dict[str, str]:
    """Return restrictive headers for a browser-facing response.

    Parameters
    ----------
    script_nonce : str | None, optional
        Random value that also appears on the page's ``<script>`` tag. When
        given, the Content Security Policy allows that one script and nothing
        else, so injected script tags do not run.

    Returns
    -------
    dict[str, str]
        Header names and values to attach to the response.
    """
    content_security_policy = [
        "default-src 'none'",
        "style-src 'unsafe-inline'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "form-action 'self'",
        "base-uri 'none'",
        "frame-ancestors 'none'",
    ]
    if script_nonce is not None:
        content_security_policy.append(f"script-src 'nonce-{script_nonce}'")

    return {
        "Cache-Control": "no-store",
        "Pragma": "no-cache",
        "Referrer-Policy": "same-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": "; ".join(content_security_policy),
    }


def client_ip(request: Request, trust_forwarded_headers: bool) -> str:
    """Return the client address that failed-login limits are counted against.

    Parameters
    ----------
    request : Request
        Current request.
    trust_forwarded_headers : bool
        Whether proxy headers may be believed. Only turn this on behind a
        proxy you control; otherwise any client can set these headers and
        spend another client's failed-login budget.

    Returns
    -------
    str
        Client address, or ``"unknown"`` when no address is available.
    """
    headers = getattr(request, "headers", {})
    if trust_forwarded_headers:
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
        correctly served page would look insecure.

    Returns
    -------
    bool
        ``True`` when the browser connection used HTTPS.
    """
    if request.url.scheme == "https":
        return True
    if not trust_forwarded_headers:
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
