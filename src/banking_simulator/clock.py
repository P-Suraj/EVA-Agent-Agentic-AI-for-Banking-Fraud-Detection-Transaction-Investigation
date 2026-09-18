"""
Deterministic Simulated Clock.

Provides reproducible ISO-8601 timestamps without calling system datetime.now().
"""

from datetime import datetime, timedelta, timezone


class SimulatedClock:
    """
    In-memory clock providing deterministic, reproducible timestamps.
    """

    DEFAULT_EPOCH = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def __init__(self, start_time: datetime | None = None):
        self._current_time = start_time or self.DEFAULT_EPOCH

    def tick(self, seconds: int = 1) -> str:
        """Advance time by a specified number of seconds and return the new ISO timestamp."""
        self._current_time += timedelta(seconds=seconds)
        return self.now_iso()

    def now_iso(self) -> str:
        """Return the current simulated time as an ISO-8601 string."""
        return self._current_time.isoformat()
