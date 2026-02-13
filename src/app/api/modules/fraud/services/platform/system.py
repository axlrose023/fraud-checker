from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.core import create_signal
from app.api.modules.fraud.services.network.user_agent import is_chromium_ua

SOFTWARE_RENDERER_MARKERS = ("swiftshader", "llvmpipe", "software")


class SystemFingerprintService:
    def collect(
        self,
        payload: FraudCheckRequest,
        ua: str,
        is_desktop_ua: bool,
    ) -> list[FraudSignal]:
        signals: list[FraudSignal] = []

        if payload.navigator.hardware_concurrency is not None:
            if payload.navigator.hardware_concurrency <= 1:
                signals.append(
                    create_signal(
                        code="LOW_CPU_CORE_COUNT",
                        weight=8,
                        message="Very low CPU core count for modern browsers.",
                    )
                )

        if (
            is_desktop_ua
            and payload.navigator.device_memory is not None
            and payload.navigator.device_memory <= 0.5
        ):
            signals.append(
                create_signal(
                    code="LOW_DEVICE_MEMORY_DESKTOP",
                    weight=10,
                    message="Desktop-like browser with very low device memory.",
                )
            )

        if (
            is_desktop_ua
            and payload.navigator.plugins_count is not None
            and payload.navigator.plugins_count == 0
            and is_chromium_ua(ua)
        ):
            signals.append(
                create_signal(
                    code="ZERO_PLUGINS_DESKTOP",
                    weight=12,
                    message="Desktop browser reports zero plugins.",
                )
            )

        if payload.webgl and payload.webgl.renderer:
            renderer = payload.webgl.renderer.lower()
            if any(marker in renderer for marker in SOFTWARE_RENDERER_MARKERS):
                signals.append(
                    create_signal(
                        code="SOFTWARE_WEBGL_RENDERER",
                        weight=25,
                        message="WebGL renderer indicates software rendering/emulation.",
                    )
                )

        return signals


__all__ = ("SOFTWARE_RENDERER_MARKERS", "SystemFingerprintService")
