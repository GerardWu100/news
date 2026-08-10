"""When proxy headers may be believed.

Any caller can send ``X-Forwarded-For``. Believing it from a direct connection
would let one caller spend another caller's failed-login budget, or claim an
encrypted connection that never existed.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from news.web.security import client_ip, request_is_secure

# Genuinely routable addresses. The documentation ranges such as 203.0.113.0/24
# cannot be used here: Python reports them as private, so they would be
# believed and the test would prove nothing.
PROXY_CLIENT_ADDRESS = "93.184.216.34"
DIRECT_PUBLIC_PEER = "8.8.8.8"


def _build_request(peer_address: str, headers: dict[str, str]) -> SimpleNamespace:
    """Build the smallest object the address helpers read.

    Parameters
    ----------
    peer_address : str
        Address of the machine that actually opened the connection.
    headers : dict[str, str]
        Request headers, including any forwarded-address claims.

    Returns
    -------
    SimpleNamespace
        Stand-in request with the attributes the helpers use.
    """
    return SimpleNamespace(
        client=SimpleNamespace(host=peer_address),
        headers=headers,
        url=SimpleNamespace(scheme="http"),
    )


class ForwardedAddressTests(unittest.TestCase):
    """Verify which peer is allowed to rename the client."""

    def test_a_local_proxy_may_name_the_client(self) -> None:
        """This is the reverse-proxy deployment the setting exists for."""
        for peer_address in ("127.0.0.1", "172.18.0.4", "10.1.2.3"):
            with self.subTest(peer_address=peer_address):
                request = _build_request(
                    peer_address,
                    {"X-Forwarded-For": f"{PROXY_CLIENT_ADDRESS}, 10.0.0.1"},
                )

                self.assertEqual(
                    client_ip(request, trust_forwarded_headers=True),
                    PROXY_CLIENT_ADDRESS,
                )

    def test_a_direct_public_caller_may_not_name_itself(self) -> None:
        """Otherwise the failed-login limit is bypassed by changing a header."""
        request = _build_request(
            DIRECT_PUBLIC_PEER,
            {"X-Forwarded-For": PROXY_CLIENT_ADDRESS},
        )

        self.assertEqual(
            client_ip(request, trust_forwarded_headers=True),
            DIRECT_PUBLIC_PEER,
        )

    def test_the_setting_off_ignores_the_headers_entirely(self) -> None:
        """The peer address is the only claim that needs no trust."""
        request = _build_request(
            "127.0.0.1",
            {"X-Forwarded-For": PROXY_CLIENT_ADDRESS},
        )

        self.assertEqual(
            client_ip(request, trust_forwarded_headers=False),
            "127.0.0.1",
        )

    def test_cloudflare_header_follows_the_same_rule(self) -> None:
        """Both forwarded-address headers are claims from the same place."""
        trusted = _build_request(
            "127.0.0.1",
            {"CF-Connecting-IP": PROXY_CLIENT_ADDRESS},
        )
        untrusted = _build_request(
            DIRECT_PUBLIC_PEER,
            {"CF-Connecting-IP": PROXY_CLIENT_ADDRESS},
        )

        self.assertEqual(
            client_ip(trusted, trust_forwarded_headers=True),
            PROXY_CLIENT_ADDRESS,
        )
        self.assertEqual(
            client_ip(untrusted, trust_forwarded_headers=True),
            DIRECT_PUBLIC_PEER,
        )


class ForwardedProtocolTests(unittest.TestCase):
    """Verify who may claim that the browser connection was encrypted."""

    def test_a_local_proxy_may_report_https(self) -> None:
        """A proxy that terminates HTTPS forwards plain HTTP to this server."""
        request = _build_request("127.0.0.1", {"X-Forwarded-Proto": "https"})

        self.assertTrue(request_is_secure(request, trust_forwarded_headers=True))

    def test_a_direct_public_caller_may_not_report_https(self) -> None:
        """A false claim would put the session cookie on a plain connection."""
        request = _build_request(DIRECT_PUBLIC_PEER, {"X-Forwarded-Proto": "https"})

        self.assertFalse(request_is_secure(request, trust_forwarded_headers=True))

    def test_a_real_https_connection_needs_no_header(self) -> None:
        """The scheme the server itself saw is not a claim from anyone."""
        request = _build_request(DIRECT_PUBLIC_PEER, {})
        request.url = SimpleNamespace(scheme="https")

        self.assertTrue(request_is_secure(request, trust_forwarded_headers=False))


if __name__ == "__main__":
    unittest.main()
