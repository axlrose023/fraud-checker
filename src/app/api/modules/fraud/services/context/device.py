from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.core import create_signal
from app.api.modules.fraud.services.network.user_agent import (
    is_android_ua,
    is_desktop_mac_ua,
    is_ios_ua,
    is_tablet_ua,
)

ANDROID_PLATFORM_MARKERS = ("android", "linux")
IOS_PLATFORM_MARKERS = ("iphone", "ipad", "ipod", "macintel")


def exceeds_screen(value: int, screen_value: int, tolerance: int) -> bool:
    return value > screen_value + tolerance


def invalid_available_dimension(avail_value: int | None, screen_value: int) -> bool:
    if avail_value is None:
        return False
    return avail_value > screen_value + 20


def platform_family_from_user_agent(ua: str) -> str | None:
    marker = ua.lower()
    if "android" in marker:
        return "android"
    if "iphone" in marker or "ipad" in marker or "ipod" in marker:
        return "apple"
    if "windows" in marker:
        return "windows"
    if "macintosh" in marker:
        return "apple"
    if "cros" in marker:
        return "chromeos"
    if "linux" in marker:
        return "linux"
    return None


def platform_family_from_navigator(platform: str) -> str | None:
    marker = platform.lower()
    if not marker:
        return None
    if marker.startswith("win"):
        return "windows"
    if "android" in marker:
        return "android"
    if "cros" in marker:
        return "chromeos"
    if "linux" in marker or "x11" in marker:
        return "linux"
    if any(item in marker for item in ("mac", "iphone", "ipad", "ipod", "macintel")):
        return "apple"
    return None


def platform_family_from_client_hints(platform: str) -> str | None:
    marker = platform.strip().strip('"').lower()
    if not marker:
        return None
    if marker in {"windows"}:
        return "windows"
    if marker in {"android"}:
        return "android"
    if marker in {"ios", "macos"}:
        return "apple"
    if marker in {"linux"}:
        return "linux"
    if marker in {"chrome os", "chromeos", "cros"}:
        return "chromeos"
    return None


class DeviceConsistencyService:
    def collect(
        self,
        payload: FraudCheckRequest,
        ua: str,
        platform: str,
        is_mobile_ua: bool,
    ) -> list[FraudSignal]:
        signals: list[FraudSignal] = []

        tablet_ua = is_tablet_ua(ua)
        max_width = max(payload.viewport.width, payload.screen.width)
        if is_mobile_ua and not tablet_ua and max_width >= 1280:
            signals.append(
                create_signal(
                    code="MOBILE_UA_DESKTOP_VIEWPORT",
                    weight=30,
                    message="Mobile User-Agent with desktop-sized viewport/screen.",
                )
            )

        if (
            payload.client_hints
            and payload.client_hints.mobile is not None
            and bool(payload.client_hints.mobile) != (is_mobile_ua and not tablet_ua)
        ):
            signals.append(
                create_signal(
                    code="UA_CLIENT_HINTS_MISMATCH",
                    weight=20,
                    message="Client hints mobile flag is inconsistent with User-Agent.",
                )
            )

        if payload.client_hints and payload.client_hints.platform:
            ua_family = platform_family_from_user_agent(ua)
            ch_family = platform_family_from_client_hints(payload.client_hints.platform)
            if ua_family and ch_family and ua_family != ch_family:
                signals.append(
                    create_signal(
                        code="UA_CH_PLATFORM_MISMATCH",
                        weight=20,
                        message="Client hints platform is inconsistent with User-Agent platform.",
                    )
                )

            nav_family = platform_family_from_navigator(platform)
            if (
                nav_family
                and ch_family
                and not (ua_family == "android" and nav_family == "linux" and ch_family == "android")
                and nav_family != ch_family
            ):
                signals.append(
                    create_signal(
                        code="NAV_CH_PLATFORM_MISMATCH",
                        weight=15,
                        message=(
                            "Client hints platform is inconsistent with navigator.platform."
                        ),
                    )
                )

        if exceeds_screen(payload.viewport.width, payload.screen.width, 120):
            signals.append(
                create_signal(
                    code="VIEWPORT_EXCEEDS_SCREEN_WIDTH",
                    weight=15,
                    message="Viewport width significantly exceeds screen width.",
                )
            )

        if exceeds_screen(payload.viewport.height, payload.screen.height, 160):
            signals.append(
                create_signal(
                    code="VIEWPORT_EXCEEDS_SCREEN_HEIGHT",
                    weight=12,
                    message="Viewport height significantly exceeds screen height.",
                )
            )

        if (
            payload.screen.avail_width is not None
            and exceeds_screen(payload.viewport.width, payload.screen.avail_width, 240)
        ):
            signals.append(
                create_signal(
                    code="VIEWPORT_EXCEEDS_SCREEN_AVAIL_WIDTH",
                    weight=8,
                    message="Viewport width significantly exceeds screen.availWidth.",
                )
            )

        if (
            payload.screen.avail_height is not None
            and exceeds_screen(payload.viewport.height, payload.screen.avail_height, 320)
        ):
            signals.append(
                create_signal(
                    code="VIEWPORT_EXCEEDS_SCREEN_AVAIL_HEIGHT",
                    weight=8,
                    message="Viewport height significantly exceeds screen.availHeight.",
                )
            )

        if invalid_available_dimension(payload.screen.avail_width, payload.screen.width):
            signals.append(
                create_signal(
                    code="SCREEN_AVAIL_WIDTH_INVALID",
                    weight=12,
                    message="screen.availWidth is larger than screen.width.",
                )
            )

        if invalid_available_dimension(payload.screen.avail_height, payload.screen.height):
            signals.append(
                create_signal(
                    code="SCREEN_AVAIL_HEIGHT_INVALID",
                    weight=12,
                    message="screen.availHeight is larger than screen.height.",
                )
            )

        if payload.screen.pixel_ratio and payload.screen.pixel_ratio > 5:
            signals.append(
                create_signal(
                    code="UNUSUAL_PIXEL_RATIO",
                    weight=10,
                    message="Reported device pixel ratio is unusually high.",
                )
            )

        if is_mobile_ua and payload.navigator.max_touch_points == 0:
            signals.append(
                create_signal(
                    code="MOBILE_UA_ZERO_TOUCH_POINTS",
                    weight=15,
                    message="Mobile User-Agent reports zero touch points.",
                )
            )

        if not is_mobile_ua and (payload.navigator.max_touch_points or 0) >= 10:
            signals.append(
                create_signal(
                    code="DESKTOP_UA_HIGH_TOUCH_POINTS",
                    weight=8,
                    message="Desktop User-Agent reports unusually high touch points.",
                )
            )

        if not is_mobile_ua and payload.viewport.width <= 420 and payload.viewport.height <= 420:
            signals.append(
                create_signal(
                    code="TINY_VIEWPORT_DESKTOP",
                    weight=6,
                    message="Desktop-like UA with an unusually small viewport.",
                )
            )

        if is_android_ua(ua) and platform and not any(
            marker in platform for marker in ANDROID_PLATFORM_MARKERS
        ):
            signals.append(
                create_signal(
                    code="UA_PLATFORM_MISMATCH_ANDROID",
                    weight=15,
                    message="UA claims Android but navigator.platform differs.",
                )
            )

        if is_ios_ua(ua) and platform and not any(
            marker in platform for marker in IOS_PLATFORM_MARKERS
        ):
            signals.append(
                create_signal(
                    code="UA_PLATFORM_MISMATCH_IOS",
                    weight=15,
                    message="UA claims iOS but navigator.platform differs.",
                )
            )

        if "windows" in ua and platform and "win" not in platform:
            signals.append(
                create_signal(
                    code="UA_PLATFORM_MISMATCH_WINDOWS",
                    weight=15,
                    message="UA claims Windows but navigator.platform differs.",
                )
            )

        if is_desktop_mac_ua(ua) and platform and "mac" not in platform:
            signals.append(
                create_signal(
                    code="UA_PLATFORM_MISMATCH_MAC",
                    weight=15,
                    message="UA claims desktop macOS but navigator.platform differs.",
                )
            )

        if (
            "linux" in ua
            and not is_android_ua(ua)
            and platform
            and "linux" not in platform
            and "x11" not in platform
        ):
            signals.append(
                create_signal(
                    code="UA_PLATFORM_MISMATCH_LINUX",
                    weight=15,
                    message="UA claims Linux but navigator.platform differs.",
                )
            )

        return signals


__all__ = ("DeviceConsistencyService",)
