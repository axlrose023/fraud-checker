from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from app.api.modules.fraud.service import FraudFacadeService
from app.api.modules.fraud.services.automation import AutomationChecksService
from app.api.modules.fraud.services.collectors import (
    ClientChecksCollector,
    NetworkChecksCollector,
)
from app.api.modules.fraud.services.context.device import DeviceConsistencyService
from app.api.modules.fraud.services.context.geo import GeoConsistencyService
from app.api.modules.fraud.services.context.ip import IpConsistencyService
from app.api.modules.fraud.services.context.locale import LocaleConsistencyService
from app.api.modules.fraud.services.network import (
    InMemoryIpRateLimiter,
    IpGeoClient,
    RequestIpResolver,
)
from app.api.modules.fraud.services.network.headers import HeaderConsistencyService
from app.api.modules.fraud.services.platform.system import SystemFingerprintService
from app.api.modules.fraud.services.platform.timestamp import (
    TimestampConsistencyService,
)
from app.clients.providers import HttpClientsProvider
from app.settings import Config, get_config


class AppProvider(Provider):
    """Application provider for dependency injection."""

    @provide(scope=Scope.APP)
    def get_config(self) -> Config:
        return get_config()


class ServicesProvider(Provider):
    """Services provider for dependency injection."""

    @provide(scope=Scope.APP)
    def get_fraud_rate_limiter(self, config: Config) -> InMemoryIpRateLimiter:
        return InMemoryIpRateLimiter(
            window_seconds=config.fraud.rate_limit_window_seconds,
            max_requests_per_ip=config.fraud.rate_limit_max_requests_per_ip,
        )

    @provide(scope=Scope.APP)
    def get_request_ip_resolver(self, config: Config) -> RequestIpResolver:
        return RequestIpResolver(config)

    @provide(scope=Scope.APP)
    def get_automation_checks_service(self) -> AutomationChecksService:
        return AutomationChecksService()

    @provide(scope=Scope.APP)
    def get_device_checks_service(self) -> DeviceConsistencyService:
        return DeviceConsistencyService()

    @provide(scope=Scope.APP)
    def get_locale_checks_service(self) -> LocaleConsistencyService:
        return LocaleConsistencyService()

    @provide(scope=Scope.APP)
    def get_header_checks_service(self) -> HeaderConsistencyService:
        return HeaderConsistencyService()

    @provide(scope=Scope.APP)
    def get_timestamp_checks_service(self) -> TimestampConsistencyService:
        return TimestampConsistencyService()

    @provide(scope=Scope.APP)
    def get_system_checks_service(self) -> SystemFingerprintService:
        return SystemFingerprintService()

    @provide(scope=Scope.APP)
    def get_ip_checks_service(self) -> IpConsistencyService:
        return IpConsistencyService()

    @provide(scope=Scope.APP)
    def get_geo_checks_service(self) -> GeoConsistencyService:
        return GeoConsistencyService()

    @provide(scope=Scope.APP)
    def get_fraud_client_checks_service(
        self,
        automation_checks: AutomationChecksService,
        device_checks: DeviceConsistencyService,
        locale_checks: LocaleConsistencyService,
        header_checks: HeaderConsistencyService,
        timestamp_checks: TimestampConsistencyService,
        system_checks: SystemFingerprintService,
        ip_checks: IpConsistencyService,
    ) -> ClientChecksCollector:
        return ClientChecksCollector(
            automation_checks=automation_checks,
            device_checks=device_checks,
            locale_checks=locale_checks,
            header_checks=header_checks,
            timestamp_checks=timestamp_checks,
            system_checks=system_checks,
            ip_checks=ip_checks,
        )

    @provide(scope=Scope.REQUEST)
    def get_fraud_network_checks_service(
        self,
        ip_geo_client: IpGeoClient,
        geo_checks: GeoConsistencyService,
    ) -> NetworkChecksCollector:
        return NetworkChecksCollector(
            ip_geo_client=ip_geo_client,
            geo_checks=geo_checks,
        )

    @provide(scope=Scope.REQUEST)
    def get_fraud_facade_service(
        self,
        config: Config,
        fraud_rate_limiter: InMemoryIpRateLimiter,
        request_ip_resolver: RequestIpResolver,
        client_checks: ClientChecksCollector,
        network_checks: NetworkChecksCollector,
    ) -> FraudFacadeService:
        return FraudFacadeService(
            config=config,
            rate_limiter=fraud_rate_limiter,
            ip_resolver=request_ip_resolver,
            client_checks=client_checks,
            network_checks=network_checks,
        )


def get_async_container() -> AsyncContainer:
    return make_async_container(
        AppProvider(),
        ServicesProvider(),
        HttpClientsProvider(),
    )
