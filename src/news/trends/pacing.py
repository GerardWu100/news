"""Keep a minimum gap between outgoing Google Trends requests.

Google's Trends endpoints are unofficial and rate limit hard: a short burst of
requests starts returning HTTP 429, and the block lasts long enough to ruin a
session. Spacing the calls out is the cheapest way to avoid that, and it is
what this module does.

The gap is enforced across threads on purpose. The API serves the trends route
with a plain synchronous handler, which FastAPI runs in its worker thread pool,
so several browser requests can reach the client at once. One shared pacer with
a lock turns those into an orderly queue instead of a burst.
"""

from __future__ import annotations

import threading
import time

# A conservative default gap. Repeated probing of the live endpoints showed a
# few seconds between calls is enough to avoid HTTP 429 for ordinary use.
DEFAULT_SECONDS_BETWEEN_REQUESTS = 4.0


class RequestPacer:
    """Delay each caller until the minimum gap since the last request passed.

    Attributes
    ----------
    minimum_gap_seconds : float
        Shortest permitted time between the start of two requests.
    """

    __slots__ = ("minimum_gap_seconds", "_lock", "_next_allowed_time")

    def __init__(
        self,
        minimum_gap_seconds: float = DEFAULT_SECONDS_BETWEEN_REQUESTS,
    ) -> None:
        """Create a pacer.

        Parameters
        ----------
        minimum_gap_seconds : float, optional
            Shortest permitted gap in seconds. Zero disables pacing, which is
            what the offline tests use so they do not sleep.
        """
        if minimum_gap_seconds < 0:
            raise ValueError("minimum_gap_seconds cannot be negative.")
        self.minimum_gap_seconds = minimum_gap_seconds
        self._lock = threading.Lock()
        # Monotonic clock, so a system time change cannot make the gap wrong.
        self._next_allowed_time = 0.0

    def wait_for_turn(self) -> None:
        """Block until this caller may issue its request.

        The lock is deliberately held while sleeping. That serializes waiting
        callers, so ten threads arriving together leave one gap between each
        rather than all waking at the same moment.
        """
        if self.minimum_gap_seconds == 0:
            return

        with self._lock:
            now = time.monotonic()
            seconds_to_wait = self._next_allowed_time - now
            if seconds_to_wait > 0:
                time.sleep(seconds_to_wait)
                now = self._next_allowed_time
            self._next_allowed_time = now + self.minimum_gap_seconds
