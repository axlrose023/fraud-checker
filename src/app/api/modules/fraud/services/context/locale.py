from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.core import create_signal


def language_base(language: str) -> str:
    return language.split("-", 1)[0].lower()


def timezone_offset_minutes(timezone_name: str, at: datetime | None = None) -> int | None:
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:  # noqa: BLE001
        return None

    target_dt = at or datetime.now(UTC)
    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=UTC)

    offset = target_dt.astimezone(tz).utcoffset()
    if offset is None:
        return None
    return int(offset.total_seconds() / 60)


def extract_primary_language(accept_language: str) -> str | None:
    first_token = accept_language.split(",", 1)[0].strip()
    if not first_token:
        return None
    language = first_token.split(";", 1)[0].strip()
    return language or None


class LocaleConsistencyService:
    def collect(self, payload: FraudCheckRequest) -> list[FraudSignal]:
        signals: list[FraudSignal] = []

        language = payload.navigator.language
        languages = payload.navigator.languages

        if not language and not languages:
            signals.append(
                create_signal(
                    code="MISSING_LANGUAGE_DATA",
                    weight=10,
                    message="Browser language signals are missing.",
                )
            )

        if language and languages:
            language_bases = {language_base(item) for item in languages}
            if language_base(language) not in language_bases:
                signals.append(
                    create_signal(
                        code="LANGUAGE_MISMATCH",
                        weight=10,
                        message="navigator.language is inconsistent with navigator.languages.",
                    )
                )

        location = payload.location
        if not location or not location.timezone or location.utc_offset_minutes is None:
            return signals

        expected_offset = timezone_offset_minutes(location.timezone, at=payload.collected_at)
        if expected_offset is None:
            return signals

        if abs(expected_offset - location.utc_offset_minutes) > 60:
            signals.append(
                create_signal(
                    code="TIMEZONE_OFFSET_MISMATCH",
                    weight=20,
                    message="Reported timezone and UTC offset are inconsistent.",
                )
            )

        return signals


__all__ = (
    "LocaleConsistencyService",
    "extract_primary_language",
    "language_base",
    "timezone_offset_minutes",
)
