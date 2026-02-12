from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.context.geo import GeoConsistencyService
from app.api.modules.fraud.services.network import IpGeoClient, IpGeoResult


class NetworkChecksCollector:
    def __init__(
        self,
        ip_geo_client: IpGeoClient,
        geo_checks: GeoConsistencyService,
    ):
        self._ip_geo_client = ip_geo_client
        self._geo_checks = geo_checks

    async def collect(
        self,
        payload: FraudCheckRequest,
        request_ip: str | None,
    ) -> tuple[list[FraudSignal], IpGeoResult | None]:
        ip_geo: IpGeoResult | None = None
        if request_ip:
            ip_geo = await self._ip_geo_client.resolve(request_ip)

        signals = self._geo_checks.collect(payload=payload, ip_geo=ip_geo)
        return signals, ip_geo


__all__ = ("NetworkChecksCollector",)
