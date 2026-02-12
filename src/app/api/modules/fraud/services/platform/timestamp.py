from datetime import UTC, datetime, timedelta

from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.core import create_signal


class TimestampConsistencyService:
    def collect(
        self,
        payload: FraudCheckRequest,
        now: datetime | None = None,
    ) -> list[FraudSignal]:
        if payload.collected_at is None:
            return []

        evaluation_time = now or datetime.now(UTC)
        collected_at = payload.collected_at
        if collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=UTC)

        if collected_at > evaluation_time + timedelta(minutes=2):
            return [
                create_signal(
                    code="CLIENT_TIMESTAMP_IN_FUTURE",
                    weight=12,
                    message="Client snapshot timestamp is too far in the future.",
                )
            ]

        if evaluation_time - collected_at > timedelta(minutes=10):
            return [
                create_signal(
                    code="STALE_CLIENT_SNAPSHOT",
                    weight=18,
                    message="Client snapshot looks stale and may be replayed.",
                )
            ]

        return []


__all__ = ("TimestampConsistencyService",)
