"""Regression tests for outbound retry behavior."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import httpx
from news.sources.retry import get_with_retry


class _StubAsyncClient:
    """Tiny async client stub for retry tests."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.calls = 0

    async def get(self, _url: str, **_kwargs: object) -> httpx.Response:
        """Return the next queued object or raise it if it is an exception."""
        self.calls += 1
        next_item = self.responses.pop(0)
        if isinstance(next_item, Exception):
            raise next_item
        return next_item


class RetryTests(unittest.IsolatedAsyncioTestCase):
    """Test transient retry behavior."""

    async def test_retries_timeout_then_succeeds(self) -> None:
        """Timeouts should be retried before failing the request."""
        request = httpx.Request("GET", "https://example.com")
        client = _StubAsyncClient(
            [
                httpx.ReadTimeout("timed out", request=request),
                httpx.Response(200, json={"ok": True}, request=request),
            ]
        )

        with patch("news.sources.retry.asyncio.sleep", new=AsyncMock()) as sleep:
            response = await get_with_retry(client, "https://example.com")

        self.assertEqual(client.calls, 2)
        sleep.assert_awaited_once()
        self.assertEqual(response.status_code, 200)

    async def test_retries_http_500_then_succeeds(self) -> None:
        """HTTP 5xx responses should be retried."""
        request = httpx.Request("GET", "https://example.com")
        client = _StubAsyncClient(
            [
                httpx.Response(503, request=request),
                httpx.Response(200, json={"ok": True}, request=request),
            ]
        )

        with patch("news.sources.retry.asyncio.sleep", new=AsyncMock()) as sleep:
            response = await get_with_retry(client, "https://example.com")

        self.assertEqual(client.calls, 2)
        sleep.assert_awaited_once()
        self.assertEqual(response.status_code, 200)

    async def test_does_not_retry_http_400(self) -> None:
        """Client errors should fail immediately."""
        request = httpx.Request("GET", "https://example.com")
        client = _StubAsyncClient([httpx.Response(400, request=request)])

        with (
            patch("news.sources.retry.asyncio.sleep", new=AsyncMock()) as sleep,
            self.assertRaises(httpx.HTTPStatusError),
        ):
            await get_with_retry(client, "https://example.com")

        self.assertEqual(client.calls, 1)
        sleep.assert_not_awaited()

    async def test_raises_after_final_retryable_failure(self) -> None:
        """The final retryable error should reach the caller unchanged."""
        request = httpx.Request("GET", "https://example.com")
        responses = [httpx.Response(503, request=request) for _ in range(3)]
        client = _StubAsyncClient(responses)

        with (
            patch("news.sources.retry.asyncio.sleep", new=AsyncMock()) as sleep,
            self.assertRaises(httpx.HTTPStatusError) as context,
        ):
            await get_with_retry(client, "https://example.com")

        self.assertEqual(client.calls, 3)
        self.assertEqual(sleep.await_count, 2)
        self.assertIs(context.exception.response, responses[-1])
