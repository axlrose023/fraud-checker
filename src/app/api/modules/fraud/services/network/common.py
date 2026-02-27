from collections.abc import Mapping
from ipaddress import ip_address

from fastapi import Request

from app.settings import Config


def normalize_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    return {str(k).lower(): str(v) for k, v in headers.items()}


def normalize_text(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def normalize_ip(value: str | None) -> str | None:
    if not value:
        return None

    candidate = value.split(",", 1)[0].strip()
    try:
        return str(ip_address(candidate))
    except ValueError:
        return None


class RequestIpResolver:
    def __init__(self, config: Config):
        self._trust_forwarded_ip = config.fraud.trust_forwarded_ip

    def get_request_ip(self, request: Request) -> str | None:
        if self._trust_forwarded_ip:
            for header in ("cf-connecting-ip", "x-forwarded-for", "x-real-ip"):
                value = request.headers.get(header)
                ip = normalize_ip(value)
                if ip:
                    return ip

        if request.client and request.client.host:
            return normalize_ip(request.client.host)

        return None


__all__ = (
    "RequestIpResolver",
    "normalize_headers",
    "normalize_ip",
    "normalize_text",
)
