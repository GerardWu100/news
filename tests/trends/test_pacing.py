"""Tests for the minimum gap kept between outgoing requests."""

from __future__ import annotations

import threading
import unittest
from unittest.mock import patch

from news.trends.pacing import RequestPacer


class RequestPacerTests(unittest.TestCase):
    """Spacing behavior, checked with a fake clock so tests do not sleep."""

    def test_first_request_does_not_wait(self) -> None:
        """Nothing has been sent yet, so there is nothing to wait for."""
        pacer = RequestPacer(4.0)

        with patch("news.trends.pacing.time.sleep") as fake_sleep:
            pacer.wait_for_turn()

        fake_sleep.assert_not_called()

    def test_second_request_waits_for_the_gap(self) -> None:
        """A request arriving immediately after another is delayed."""
        pacer = RequestPacer(4.0)
        clock_readings = iter([100.0, 100.0])

        with (
            patch("news.trends.pacing.time.monotonic", side_effect=clock_readings),
            patch("news.trends.pacing.time.sleep") as fake_sleep,
        ):
            pacer.wait_for_turn()
            pacer.wait_for_turn()

        fake_sleep.assert_called_once_with(4.0)

    def test_request_after_a_long_pause_does_not_wait(self) -> None:
        """Enough real time has passed, so no extra delay is added."""
        pacer = RequestPacer(4.0)
        clock_readings = iter([100.0, 200.0])

        with (
            patch("news.trends.pacing.time.monotonic", side_effect=clock_readings),
            patch("news.trends.pacing.time.sleep") as fake_sleep,
        ):
            pacer.wait_for_turn()
            pacer.wait_for_turn()

        fake_sleep.assert_not_called()

    def test_zero_gap_disables_pacing(self) -> None:
        """Tests and offline callers can turn the delay off entirely."""
        pacer = RequestPacer(0.0)

        with patch("news.trends.pacing.time.sleep") as fake_sleep:
            for _ in range(5):
                pacer.wait_for_turn()

        fake_sleep.assert_not_called()

    def test_negative_gap_is_rejected(self) -> None:
        """A negative gap is a configuration mistake, not a fast path."""
        with self.assertRaises(ValueError):
            RequestPacer(-1.0)

    def test_threads_are_spaced_one_gap_apart(self) -> None:
        """Concurrent callers queue instead of all firing at once.

        The API runs the trends route in a worker thread pool, so several
        browser requests can reach one client together. Each recorded sleep
        should be a full gap, which means the callers were serialized rather
        than released at the same moment.
        """
        pacer = RequestPacer(4.0)
        recorded_sleeps: list[float] = []
        current_time = [100.0]

        def fake_monotonic() -> float:
            return current_time[0]

        def fake_sleep(seconds: float) -> None:
            recorded_sleeps.append(seconds)
            current_time[0] += seconds

        with (
            patch("news.trends.pacing.time.monotonic", side_effect=fake_monotonic),
            patch("news.trends.pacing.time.sleep", side_effect=fake_sleep),
        ):
            threads = [
                threading.Thread(target=pacer.wait_for_turn) for _ in range(3)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        # Three callers means the first goes straight through and the other
        # two each wait one gap.
        self.assertEqual(len(recorded_sleeps), 2)
        self.assertTrue(all(seconds == 4.0 for seconds in recorded_sleeps))


if __name__ == "__main__":
    unittest.main()
