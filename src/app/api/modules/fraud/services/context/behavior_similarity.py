import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic

from app.api.modules.fraud.schema import BehaviorSignals, FraudSignal
from app.api.modules.fraud.services.core import create_signal
from app.settings import FraudConfig

_PURGE_EVERY = 256

_METRICS = ("max_scroll_y", "scroll_count", "keydown_count", "mouse_move_count", "touch_count")
_METRICS_COUNT = len(_METRICS)


@dataclass(slots=True)
class _BehaviorSnapshot:
    timestamp: float
    max_scroll_y: int
    scroll_count: int
    keydown_count: int
    mouse_move_count: int
    touch_count: int


class BehaviorSimilarityService:
    """Detects when the same fingerprint produces suspiciously similar
    behavioral patterns across multiple requests."""

    def __init__(self, config: FraudConfig):
        self._history_size = config.behavior_similarity_history_size
        self._window_seconds = config.behavior_similarity_window_seconds
        self._tolerance_pct = config.behavior_similarity_tolerance_pct
        self._match_ratio = config.behavior_similarity_match_ratio
        self._warn_threshold = config.behavior_similarity_warn_threshold
        self._warn_weight = config.behavior_similarity_warn_weight
        self._suspicious_threshold = config.behavior_similarity_suspicious_threshold
        self._suspicious_weight = config.behavior_similarity_suspicious_weight

        self._history: dict[str, deque[_BehaviorSnapshot]] = defaultdict(
            lambda: deque(maxlen=self._history_size)
        )
        self._lock = asyncio.Lock()
        self._call_count = 0

    def _purge_stale(self, cutoff: float) -> None:
        stale = [
            fp
            for fp, snaps in self._history.items()
            if not snaps or snaps[-1].timestamp < cutoff
        ]
        for fp in stale:
            del self._history[fp]

    @staticmethod
    def _values_are_similar(new_val: int, old_val: int, tolerance: float) -> bool:
        if new_val == 0 and old_val == 0:
            return True
        reference = max(new_val, old_val, 1)
        return abs(new_val - old_val) / reference <= tolerance

    def _count_similar(
        self,
        snapshot: _BehaviorSnapshot,
        history: deque[_BehaviorSnapshot],
    ) -> int:
        similar = 0
        for past in history:
            matching = 0
            for metric in _METRICS:
                if self._values_are_similar(
                    getattr(snapshot, metric),
                    getattr(past, metric),
                    self._tolerance_pct,
                ):
                    matching += 1
            if matching / _METRICS_COUNT >= self._match_ratio:
                similar += 1
        return similar

    async def record_and_check(
        self,
        fingerprint_id: str,
        behavior: BehaviorSignals | None,
    ) -> list[FraudSignal]:
        if not fingerprint_id or behavior is None:
            return []

        snapshot = _BehaviorSnapshot(
            timestamp=monotonic(),
            max_scroll_y=behavior.max_scroll_y or 0,
            scroll_count=behavior.scroll_count or 0,
            keydown_count=behavior.keydown_count or 0,
            mouse_move_count=behavior.mouse_move_count or 0,
            touch_count=behavior.touch_count or 0,
        )

        cutoff = monotonic() - self._window_seconds

        async with self._lock:
            self._call_count += 1
            if self._call_count >= _PURGE_EVERY:
                self._call_count = 0
                self._purge_stale(cutoff)

            history = self._history[fingerprint_id]
            while history and history[0].timestamp < cutoff:
                history.popleft()

            similar_count = self._count_similar(snapshot, history)
            history.append(snapshot)

        if similar_count >= self._suspicious_threshold:
            return [
                create_signal(
                    code="BEHAVIOR_SIMILARITY_SUSPICIOUS",
                    weight=self._suspicious_weight,
                    message=(
                        f"Fingerprint produced {similar_count} behaviorally similar "
                        f"requests. Human behavior is rarely this consistent."
                    ),
                )
            ]
        if similar_count >= self._warn_threshold:
            return [
                create_signal(
                    code="BEHAVIOR_SIMILARITY_WARN",
                    weight=self._warn_weight,
                    message=(
                        f"Fingerprint produced {similar_count} behaviorally similar "
                        f"requests, suggesting automated activity."
                    ),
                )
            ]
        return []


__all__ = ("BehaviorSimilarityService",)
