from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.core import create_signal

# Thresholds
_MIN_TIME_ON_PAGE_MS = 3000  # less than 3 seconds → suspicious
_MIN_INTERACTION_EVENTS = 3  # at least a few keydowns or mouse/touch events


class BehaviorConsistencyService:
    def collect(
        self,
        payload: FraudCheckRequest,
    ) -> list[FraudSignal]:
        bhv = payload.behavior
        if bhv is None:
            return []

        signals: list[FraudSignal] = []

        # Too fast: form submitted in under 3 seconds
        if bhv.time_on_page_ms is not None and bhv.time_on_page_ms < _MIN_TIME_ON_PAGE_MS:
            signals.append(
                create_signal(
                    code="TOO_FAST_SUBMISSION",
                    weight=25,
                    message="Page was submitted too quickly (under 3 seconds).",
                )
            )

        # No scroll on a page that requires scrolling
        if (
            bhv.scroll_count is not None
            and bhv.document_height is not None
            and bhv.scroll_count == 0
            and bhv.document_height > 1200
        ):
            viewport_h = payload.viewport.height
            if bhv.document_height > viewport_h + 200:
                signals.append(
                    create_signal(
                        code="NO_SCROLL_BEFORE_SUBMIT",
                        weight=18,
                        message="No scroll detected on a page that requires scrolling.",
                    )
                )

        # No human interaction events at all (no keys, no mouse, no touch)
        keys = bhv.keydown_count or 0
        mouse = bhv.mouse_move_count or 0
        touch = bhv.touch_count or 0
        total_interaction = keys + mouse + touch

        if total_interaction < _MIN_INTERACTION_EVENTS:
            signals.append(
                create_signal(
                    code="NO_HUMAN_INTERACTION",
                    weight=30,
                    message="No keyboard, mouse, or touch events detected.",
                )
            )

        return signals


__all__ = ("BehaviorConsistencyService",)
