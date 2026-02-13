from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.automation import AutomationChecksService
from app.api.modules.fraud.services.context.behavior import BehaviorConsistencyService
from app.api.modules.fraud.services.context.device import DeviceConsistencyService
from app.api.modules.fraud.services.context.ip import IpConsistencyService
from app.api.modules.fraud.services.context.locale import LocaleConsistencyService
from app.api.modules.fraud.services.network.headers import HeaderConsistencyService
from app.api.modules.fraud.services.network.user_agent import has_mobile_ua
from app.api.modules.fraud.services.platform.system import SystemFingerprintService
from app.api.modules.fraud.services.platform.timestamp import (
    TimestampConsistencyService,
)


class ClientChecksCollector:
    def __init__(
        self,
        automation_checks: AutomationChecksService,
        device_checks: DeviceConsistencyService,
        locale_checks: LocaleConsistencyService,
        header_checks: HeaderConsistencyService,
        timestamp_checks: TimestampConsistencyService,
        system_checks: SystemFingerprintService,
        ip_checks: IpConsistencyService,
        behavior_checks: BehaviorConsistencyService,
    ):
        self._automation_checks = automation_checks
        self._device_checks = device_checks
        self._locale_checks = locale_checks
        self._header_checks = header_checks
        self._timestamp_checks = timestamp_checks
        self._system_checks = system_checks
        self._ip_checks = ip_checks
        self._behavior_checks = behavior_checks

    def collect(
        self,
        payload: FraudCheckRequest,
        request_ip: str | None,
        headers: dict[str, str],
    ) -> list[FraudSignal]:
        ua = payload.navigator.user_agent.lower()
        platform = (payload.navigator.platform or "").lower()

        is_mobile_ua = has_mobile_ua(ua)
        is_desktop_ua = not is_mobile_ua

        signals: list[FraudSignal] = []
        signals.extend(self._automation_checks.collect(payload=payload, ua=ua))
        signals.extend(
            self._device_checks.collect(
                payload=payload,
                ua=ua,
                platform=platform,
                is_mobile_ua=is_mobile_ua,
            )
        )
        signals.extend(self._locale_checks.collect(payload=payload))
        signals.extend(self._header_checks.collect(payload=payload, headers=headers))
        signals.extend(self._timestamp_checks.collect(payload=payload))
        signals.extend(
            self._system_checks.collect(
                payload=payload,
                ua=ua,
                is_desktop_ua=is_desktop_ua,
            )
        )
        signals.extend(
            self._ip_checks.collect(
                payload=payload,
                request_ip=request_ip,
            )
        )
        signals.extend(self._behavior_checks.collect(payload=payload))
        return signals


__all__ = ("ClientChecksCollector",)
