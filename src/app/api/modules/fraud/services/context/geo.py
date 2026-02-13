from math import asin, cos, radians, sin, sqrt

from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.core import create_signal
from app.api.modules.fraud.services.network import IpGeoResult


def haversine_distance_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    # Great-circle distance using the Haversine formula.
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


class GeoConsistencyService:
    def collect(
        self,
        payload: FraudCheckRequest,
        ip_geo: IpGeoResult | None,
    ) -> list[FraudSignal]:
        if ip_geo is None:
            return []

        signals: list[FraudSignal] = []

        if ip_geo.is_hosting:
            signals.append(
                create_signal(
                    code="HOSTING_PROVIDER_IP",
                    weight=20,
                    message="IP appears to belong to a hosting/data-center provider.",
                )
            )

        if not payload.location:
            return signals

        if payload.location.country_iso and ip_geo.country_iso:
            if payload.location.country_iso.upper() != ip_geo.country_iso.upper():
                signals.append(
                    create_signal(
                        code="IP_COUNTRY_MISMATCH",
                        weight=35,
                        message="Location country does not match IP geolocation country.",
                    )
                )

        if payload.location.timezone and ip_geo.timezone:
            if payload.location.timezone != ip_geo.timezone:
                signals.append(
                    create_signal(
                        code="IP_TIMEZONE_MISMATCH",
                        weight=15,
                        message="Reported timezone does not match IP geolocation timezone.",
                    )
                )

        if (
            payload.location.utc_offset_minutes is not None
            and ip_geo.utc_offset_minutes is not None
            and abs(payload.location.utc_offset_minutes - ip_geo.utc_offset_minutes) > 60
        ):
            signals.append(
                create_signal(
                    code="IP_UTC_OFFSET_MISMATCH",
                    weight=18,
                    message="Reported UTC offset does not match IP geolocation UTC offset.",
                )
            )

        if (
            payload.location.latitude is not None
            and payload.location.longitude is not None
            and payload.location.accuracy_meters is not None
            and payload.location.accuracy_meters <= 50_000
            and ip_geo.latitude is not None
            and ip_geo.longitude is not None
        ):
            distance_km = haversine_distance_km(
                payload.location.latitude,
                payload.location.longitude,
                ip_geo.latitude,
                ip_geo.longitude,
            )
            if distance_km >= 800:
                signals.append(
                    create_signal(
                        code="GEOLOCATION_DISTANCE_MISMATCH",
                        weight=25,
                        message=(
                            "Browser geolocation is too far from IP geolocation for the"
                            " reported accuracy."
                        ),
                    )
                )

        return signals


__all__ = ("GeoConsistencyService",)
