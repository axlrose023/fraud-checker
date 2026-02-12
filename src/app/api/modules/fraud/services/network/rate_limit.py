import asyncio
from collections import defaultdict, deque
from time import monotonic


class InMemoryIpRateLimiter:
    """Simple sliding-window limiter for public API abuse protection."""

    def __init__(self, window_seconds: int, max_requests_per_ip: int):
        self._window_seconds = window_seconds
        self._max_requests_per_ip = max_requests_per_ip
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, ip: str | None) -> bool:
        if not ip:
            return True

        now = monotonic()
        threshold = now - self._window_seconds

        async with self._lock:
            events = self._events[ip]
            while events and events[0] < threshold:
                events.popleft()

            if len(events) >= self._max_requests_per_ip:
                return False

            events.append(now)
            return True


__all__ = ("InMemoryIpRateLimiter",)

