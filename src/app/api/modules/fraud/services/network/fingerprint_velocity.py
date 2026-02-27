import asyncio
from collections import defaultdict, deque
from time import monotonic

from app.api.modules.fraud.schema import FraudSignal
from app.api.modules.fraud.services.core import create_signal
from app.settings import FraudConfig

_PURGE_EVERY = 512


class FingerprintVelocityTracker:
    """In-memory sliding-window counter per fingerprint_id.

    Returns escalating fraud signals when a single device fingerprint
    makes too many requests within the configured time window.
    """

    def __init__(self, config: FraudConfig):
        self._window_seconds = config.fingerprint_velocity_window_seconds
        self._thresholds: list[tuple[int, int, str]] = sorted(
            [
                (
                    config.fingerprint_velocity_critical_threshold,
                    config.fingerprint_velocity_critical_weight,
                    "FINGERPRINT_VELOCITY_CRITICAL",
                ),
                (
                    config.fingerprint_velocity_suspicious_threshold,
                    config.fingerprint_velocity_suspicious_weight,
                    "FINGERPRINT_VELOCITY_SUSPICIOUS",
                ),
                (
                    config.fingerprint_velocity_warn_threshold,
                    config.fingerprint_velocity_warn_weight,
                    "FINGERPRINT_VELOCITY_WARN",
                ),
            ],
            key=lambda t: t[0],
            reverse=True,
        )
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._call_count = 0

    def _purge_stale(self, cutoff: float) -> None:
        stale = [
            fp for fp, evts in self._events.items() if not evts or evts[-1] < cutoff
        ]
        for fp in stale:
            del self._events[fp]

    async def record_and_check(self, fingerprint_id: str) -> list[FraudSignal]:
        if not fingerprint_id:
            return []

        now = monotonic()
        cutoff = now - self._window_seconds

        async with self._lock:
            self._call_count += 1
            if self._call_count >= _PURGE_EVERY:
                self._call_count = 0
                self._purge_stale(cutoff)

            events = self._events[fingerprint_id]
            while events and events[0] < cutoff:
                events.popleft()
            events.append(now)
            count = len(events)

        for threshold_count, weight, code in self._thresholds:
            if count >= threshold_count:
                return [
                    create_signal(
                        code=code,
                        weight=weight,
                        message=(
                            f"Fingerprint submitted {count} requests in the last "
                            f"{self._window_seconds // 60} minutes."
                        ),
                    )
                ]
        return []


__all__ = ("FingerprintVelocityTracker",)
