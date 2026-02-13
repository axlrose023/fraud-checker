import asyncio
import secrets
from dataclasses import dataclass
from time import monotonic

from app.api.modules.fraud.schema import FraudCheckResponse


@dataclass(slots=True)
class CaptchaChallenge:
    response: FraudCheckResponse
    request_ip: str | None
    origin: str | None
    expires_at: float
    attempts: int = 0


class InMemoryCaptchaChallengeStore:
    """Short-lived captcha challenges keyed by challenge_id.

    This allows a 2-step flow:
    1) /fraud/check performs fraud evaluation and may require captcha, returning challenge_id
    2) /fraud/captcha/verify verifies captcha token and finalizes the decision
       without re-evaluating fraud

    Note: per-process memory store. For multi-replica deployments, replace with Redis.
    """

    def __init__(self, ttl_seconds: int, max_attempts: int = 5):
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._max_attempts = max(1, int(max_attempts))
        self._items: dict[str, CaptchaChallenge] = {}
        self._lock = asyncio.Lock()

    @property
    def ttl_seconds(self) -> int:
        return self._ttl_seconds

    def _is_expired(self, item: CaptchaChallenge, now: float) -> bool:
        return item.expires_at <= now or item.attempts >= self._max_attempts

    def _purge_expired(self, now: float) -> None:
        if not self._items:
            return
        expired_ids = [cid for cid, item in self._items.items() if self._is_expired(item, now)]
        for cid in expired_ids:
            self._items.pop(cid, None)

    async def create(
        self,
        response: FraudCheckResponse,
        request_ip: str | None,
        origin: str | None,
    ) -> str:
        challenge_id = secrets.token_urlsafe(24)
        now = monotonic()
        item = CaptchaChallenge(
            response=response,
            request_ip=request_ip,
            origin=origin,
            expires_at=now + self._ttl_seconds,
        )

        async with self._lock:
            self._purge_expired(now)
            self._items[challenge_id] = item

        return challenge_id

    async def get(self, challenge_id: str) -> CaptchaChallenge | None:
        now = monotonic()
        async with self._lock:
            item = self._items.get(challenge_id)
            if not item:
                return None
            if self._is_expired(item, now):
                self._items.pop(challenge_id, None)
                return None
            return item

    async def increment_attempts(self, challenge_id: str) -> int | None:
        now = monotonic()
        async with self._lock:
            item = self._items.get(challenge_id)
            if not item:
                return None
            if self._is_expired(item, now):
                self._items.pop(challenge_id, None)
                return None
            item.attempts += 1
            if self._is_expired(item, now):
                self._items.pop(challenge_id, None)
            return item.attempts

    async def consume(self, challenge_id: str) -> CaptchaChallenge | None:
        """Remove and return an active challenge.

        Used after successful captcha verification (single-use).
        """
        now = monotonic()
        async with self._lock:
            item = self._items.get(challenge_id)
            if not item:
                return None
            if self._is_expired(item, now):
                self._items.pop(challenge_id, None)
                return None
            return self._items.pop(challenge_id, None)


__all__ = ("CaptchaChallenge", "InMemoryCaptchaChallengeStore")
