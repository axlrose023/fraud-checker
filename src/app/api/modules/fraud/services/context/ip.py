from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.core import create_signal
from app.api.modules.fraud.services.network import normalize_ip


class IpConsistencyService:
    def collect(
        self,
        payload: FraudCheckRequest,
        request_ip: str | None,
    ) -> list[FraudSignal]:
        client_reported_ip = normalize_ip(payload.client_reported_ip)
        normalized_request_ip = normalize_ip(request_ip)

        if (
            client_reported_ip
            and normalized_request_ip
            and client_reported_ip != normalized_request_ip
        ):
            return [
                create_signal(
                    code="CLIENT_IP_MISMATCH",
                    weight=30,
                    message="Client-reported IP differs from request source IP.",
                )
            ]

        return []


__all__ = ("IpConsistencyService",)
