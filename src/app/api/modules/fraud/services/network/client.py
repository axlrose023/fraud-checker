import logging
from dataclasses import dataclass
from time import monotonic

import httpx

from app.settings import Config

logger = logging.getLogger(__name__)


def looks_like_hosting_provider(org: str) -> bool:
    if not org:
        return False

    marker = org.lower()
    signatures = (
        "hosting",
        "data center",
        "datacenter",
        "cloud",
        "colo",
        "vpn",
        "proxy",
    )
    return any(item in marker for item in signatures)


def _parse_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def parse_utc_offset_minutes(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if len(candidate) != 5 or candidate[0] not in {"+", "-"}:
        return None
    sign = 1 if candidate[0] == "+" else -1
    try:
        hours = int(candidate[1:3])
        minutes = int(candidate[3:5])
    except ValueError:
        return None
    if hours > 14 or minutes >= 60:
        return None
    return sign * (hours * 60 + minutes)


@dataclass(slots=True)
class IpGeoResult:
    country_iso: str | None
    is_hosting: bool
    timezone: str | None
    utc_offset_minutes: int | None
    latitude: float | None
    longitude: float | None


_GEO_CACHE_MAX_SIZE = 4096


class IpGeoClient:
    def __init__(self, client: httpx.AsyncClient, config: Config):
        self._enabled = config.fraud.ip_geolocation_enabled
        self._client = client
        self._base_url = config.fraud.ip_geolocation_base_url.rstrip("/")
        self._timeout = config.fraud.ip_geolocation_timeout_seconds
        self._cache_ttl_seconds = config.fraud.ip_geolocation_cache_ttl_seconds
        self._cache: dict[str, tuple[float, IpGeoResult]] = {}

    async def resolve(self, ip: str) -> IpGeoResult | None:
        if not self._enabled:
            return None

        now = monotonic()
        if self._cache_ttl_seconds > 0:
            cached = self._cache.get(ip)
            if cached and cached[0] > now:
                return cached[1]

        url = f"{self._base_url}/{ip}/json/"
        try:
            response = await self._client.get(
                url,
                timeout=self._timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to resolve IP geolocation", extra={"ip": ip})
            logger.debug("IP geolocation lookup failed: %s", exc)
            return None

        data = response.json()
        if data.get("error"):
            return None

        country_iso = data.get("country_code")
        if isinstance(country_iso, str):
            country_iso = country_iso.upper()
        else:
            country_iso = None

        org = str(data.get("org") or "")
        is_hosting = looks_like_hosting_provider(org)

        timezone = data.get("timezone")
        if not isinstance(timezone, str):
            timezone = None

        utc_offset_minutes = parse_utc_offset_minutes(data.get("utc_offset"))
        latitude = _parse_float(data.get("latitude"))
        longitude = _parse_float(data.get("longitude"))

        result = IpGeoResult(
            country_iso=country_iso,
            is_hosting=is_hosting,
            timezone=timezone,
            utc_offset_minutes=utc_offset_minutes,
            latitude=latitude,
            longitude=longitude,
        )

        if self._cache_ttl_seconds > 0:
            if len(self._cache) >= _GEO_CACHE_MAX_SIZE:
                cutoff = now
                stale = [k for k, (exp, _) in self._cache.items() if exp <= cutoff]
                for k in stale:
                    del self._cache[k]
                if len(self._cache) >= _GEO_CACHE_MAX_SIZE:
                    oldest = min(self._cache, key=lambda k: self._cache[k][0])
                    del self._cache[oldest]
            self._cache[ip] = (now + self._cache_ttl_seconds, result)

        return result


__all__ = ("IpGeoClient", "IpGeoResult")
