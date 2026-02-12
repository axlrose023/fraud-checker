from collections.abc import Mapping
from datetime import UTC, datetime

from fastapi import Request

from app.api.modules.fraud.schema import FraudCheckRequest, FraudCheckResponse
from app.api.modules.fraud.services.collectors import (
    ClientChecksCollector,
    NetworkChecksCollector,
)
from app.api.modules.fraud.services.core import (
    build_fingerprint,
    create_signal,
    decision_for_score,
)
from app.api.modules.fraud.services.network import (
    InMemoryIpRateLimiter,
    RequestIpResolver,
    normalize_headers,
)
from app.settings import Config


class FraudFacadeService:
    def __init__(
        self,
        config: Config,
        rate_limiter: InMemoryIpRateLimiter,
        ip_resolver: RequestIpResolver,
        client_checks: ClientChecksCollector,
        network_checks: NetworkChecksCollector,
    ):
        self._config = config
        self._rate_limiter = rate_limiter
        self._ip_resolver = ip_resolver
        self._client_checks = client_checks
        self._network_checks = network_checks

    async def check_request(
        self,
        request: Request,
        payload: FraudCheckRequest,
    ) -> FraudCheckResponse:
        request_ip = self._ip_resolver.get_request_ip(request)
        return await self.check(
            payload=payload,
            request_ip=request_ip,
            request_headers=request.headers,
        )

    async def check(
        self,
        payload: FraudCheckRequest,
        request_ip: str | None,
        request_headers: Mapping[str, str] | None = None,
    ) -> FraudCheckResponse:
        allowed = await self._rate_limiter.allow(request_ip)
        if not allowed:
            return FraudCheckResponse(
                decision="block",
                risk_score=100,
                fingerprint_id=build_fingerprint(payload),
                request_ip=request_ip,
                signals=[
                    create_signal(
                        code="RATE_LIMIT_EXCEEDED",
                        weight=100,
                        message="Too many requests from this IP in a short time.",
                    )
                ],
                evaluated_at=datetime.now(UTC),
            )

        headers = normalize_headers(request_headers)
        signals = self._client_checks.collect(
            payload=payload,
            request_ip=request_ip,
            headers=headers,
        )

        network_signals, ip_geo = await self._network_checks.collect(
            payload=payload,
            request_ip=request_ip,
        )
        signals.extend(network_signals)

        score = min(sum(signal.weight for signal in signals), 100)
        decision = decision_for_score(
            score=score,
            block_score_threshold=self._config.fraud.block_score_threshold,
            review_score_threshold=self._config.fraud.review_score_threshold,
        )

        return FraudCheckResponse(
            decision=decision,
            risk_score=score,
            fingerprint_id=build_fingerprint(payload),
            request_ip=request_ip,
            ip_country_iso=ip_geo.country_iso if ip_geo else None,
            signals=signals,
            evaluated_at=datetime.now(UTC),
        )
