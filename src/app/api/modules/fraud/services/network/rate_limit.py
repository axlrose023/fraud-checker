import asyncio
from collections import defaultdict, deque
from time import monotonic

_PURGE_EVERY = 512


class InMemoryIpRateLimiter:

    def __init__(self, window_seconds: int, max_requests_per_ip: int):
        self._window_seconds = window_seconds
        self._max_requests_per_ip = max_requests_per_ip
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._call_count = 0

    def _purge_stale(self, threshold: float) -> None:
        stale = [ip for ip, evts in self._events.items() if not evts or evts[-1] < threshold]
        for ip in stale:
            del self._events[ip]

    async def allow(self, ip: str | None) -> bool:
        if not ip:
            return True

        now = monotonic()
        threshold = now - self._window_seconds

        async with self._lock:
            self._call_count += 1
            if self._call_count >= _PURGE_EVERY:
                self._call_count = 0
                self._purge_stale(threshold)

            events = self._events[ip]
            while events and events[0] < threshold:
                events.popleft()

            if len(events) >= self._max_requests_per_ip:
                return False

            events.append(now)
            return True


__all__ = ("InMemoryIpRateLimiter",)

