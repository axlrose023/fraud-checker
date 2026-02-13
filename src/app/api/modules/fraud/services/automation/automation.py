from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.core import create_signal
from app.api.modules.fraud.services.network.user_agent import (
    AUTOMATION_MARKERS,
    BOT_UA_MARKERS,
    STRONG_BOT_UA_MARKERS,
    contains_any,
)


class AutomationChecksService:
    def collect(self, payload: FraudCheckRequest, ua: str) -> list[FraudSignal]:
        signals: list[FraudSignal] = []

        if payload.navigator.webdriver is True:
            signals.append(
                create_signal(
                    code="WEBDRIVER_ENABLED",
                    weight=70,
                    message="Browser reports webdriver-enabled automation.",
                )
            )

        if contains_any(ua, AUTOMATION_MARKERS):
            signals.append(
                create_signal(
                    code="AUTOMATION_UA_MARKER",
                    weight=55,
                    message="User-Agent contains known automation markers.",
                )
            )

        if contains_any(ua, STRONG_BOT_UA_MARKERS):
            signals.append(
                create_signal(
                    code="STRONG_BOT_UA_MARKER",
                    weight=85,
                    message="User-Agent matches strong non-browser bot signatures.",
                )
            )
            return signals

        if contains_any(ua, BOT_UA_MARKERS):
            signals.append(
                create_signal(
                    code="BOT_UA_MARKER",
                    weight=45,
                    message="User-Agent contains crawler/bot keywords.",
                )
            )

        return signals


__all__ = ("AutomationChecksService",)
