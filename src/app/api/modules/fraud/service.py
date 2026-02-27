import logging
from collections.abc import Mapping
from datetime import UTC, datetime

from fastapi import HTTPException, Request

from app.api.modules.fraud.models import FraudCheckLog
from app.api.modules.fraud.schema import (
    CaptchaVerifyRequest,
    FraudCheckRequest,
    FraudCheckResponse,
)
from app.api.modules.fraud.services.collectors import (
    ClientChecksCollector,
    NetworkChecksCollector,
)
from app.api.modules.fraud.services.core import (
    build_fingerprint,
    create_signal,
    decision_for_score,
)
from app.api.modules.fraud.services.core.challenge_store import (
    InMemoryCaptchaChallengeStore,
)
from app.api.modules.fraud.services.context.behavior_similarity import (
    BehaviorSimilarityService,
)
from app.api.modules.fraud.services.network import (
    FingerprintVelocityTracker,
    InMemoryIpRateLimiter,
    RequestIpResolver,
    TurnstileVerifierService,
    normalize_headers,
)
from app.database.uow import UnitOfWork
from app.settings import Config

logger = logging.getLogger(__name__)


class FraudFacadeService:
    def __init__(
        self,
        config: Config,
        rate_limiter: InMemoryIpRateLimiter,
        ip_resolver: RequestIpResolver,
        client_checks: ClientChecksCollector,
        network_checks: NetworkChecksCollector,
        turnstile_verifier: TurnstileVerifierService,
        captcha_challenges: InMemoryCaptchaChallengeStore,
        fingerprint_velocity: FingerprintVelocityTracker,
        behavior_similarity: BehaviorSimilarityService,
        uow: UnitOfWork,
    ):
        self._config = config
        self._rate_limiter = rate_limiter
        self._ip_resolver = ip_resolver
        self._client_checks = client_checks
        self._network_checks = network_checks
        self._turnstile_verifier = turnstile_verifier
        self._captcha_challenges = captcha_challenges
        self._fingerprint_velocity = fingerprint_velocity
        self._behavior_similarity = behavior_similarity
        self._uow = uow

    async def _save_log(
        self,
        response: FraudCheckResponse,
        payload: FraudCheckRequest | None = None,
        origin: str | None = None,
    ) -> None:
        try:
            log = FraudCheckLog(
                request_ip=response.request_ip,
                ip_country_iso=response.ip_country_iso,
                fingerprint_id=response.fingerprint_id,
                origin=origin,
                request_payload=payload.model_dump(mode="json") if payload else {},
                decision=response.decision,
                risk_score=response.risk_score,
                signals=[s.model_dump() for s in response.signals],
                captcha_required=response.captcha_required,
                captcha_verified=response.captcha_verified,
                challenge_id=response.challenge_id,
            )
            await self._uow.fraud_logs.create(log)
            await self._uow.commit()
        except Exception:
            logger.exception("Failed to save fraud check log")
            await self._uow.rollback()

    async def check_request(
        self,
        request: Request,
        payload: FraudCheckRequest,
    ) -> FraudCheckResponse:
        request_ip = self._ip_resolver.get_request_ip(request)
        origin = request.headers.get("origin")
        if origin and origin.strip().lower() == "null":
            origin = None
        return await self.check(
            payload=payload,
            request_ip=request_ip,
            request_headers=request.headers,
            origin=origin,
        )

    async def check(
        self,
        payload: FraudCheckRequest,
        request_ip: str | None,
        request_headers: Mapping[str, str] | None = None,
        origin: str | None = None,
    ) -> FraudCheckResponse:
        fingerprint_id = build_fingerprint(payload)

        allowed = await self._rate_limiter.allow(request_ip)
        if not allowed:
            return FraudCheckResponse(
                decision="block",
                risk_score=100,
                fingerprint_id=fingerprint_id,
                request_ip=request_ip,
                signals=[
                    create_signal(
                        code="RATE_LIMIT_EXCEEDED",
                        weight=100,
                        message="Too many requests from this IP in a short time.",
                    )
                ],
                captcha_required=False,
                captcha_verified=False,
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

        velocity_signals = await self._fingerprint_velocity.record_and_check(
            fingerprint_id,
        )
        signals.extend(velocity_signals)

        similarity_signals = await self._behavior_similarity.record_and_check(
            fingerprint_id=fingerprint_id,
            behavior=payload.behavior,
        )
        signals.extend(similarity_signals)

        score = min(sum(signal.weight for signal in signals), 100)
        decision = decision_for_score(
            score=score,
            block_score_threshold=self._config.fraud.block_score_threshold,
            review_score_threshold=self._config.fraud.review_score_threshold,
        )

        response = FraudCheckResponse(
            decision=decision,
            risk_score=score,
            fingerprint_id=fingerprint_id,
            request_ip=request_ip,
            ip_country_iso=ip_geo.country_iso if ip_geo else None,
            signals=signals,
            captcha_required=False,
            captcha_verified=False,
            evaluated_at=datetime.now(UTC),
        )
        if (
            decision == "review"
            and self._turnstile_verifier.is_configured()
            and self._captcha_challenges.ttl_seconds > 0
        ):
            challenge_id = await self._captcha_challenges.create(
                response=response.model_copy(deep=True),
                request_ip=request_ip,
                origin=origin,
            )
            response.captcha_required = True
            response.captcha_provider = self._turnstile_verifier.provider
            response.captcha_site_key = self._turnstile_verifier.site_key
            response.challenge_id = challenge_id

        await self._save_log(response=response, payload=payload, origin=origin)
        return response

    async def verify_captcha_request(
        self,
        request: Request,
        payload: CaptchaVerifyRequest,
    ) -> FraudCheckResponse:
        request_ip = self._ip_resolver.get_request_ip(request)
        origin = request.headers.get("origin")
        if origin and origin.strip().lower() == "null":
            origin = None

        challenge = await self._captcha_challenges.get(payload.challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="captcha_challenge_not_found")

        if not await self._rate_limiter.allow(request_ip):
            return FraudCheckResponse(
                decision="block",
                risk_score=100,
                fingerprint_id=challenge.response.fingerprint_id,
                request_ip=request_ip,
                signals=[
                    create_signal(
                        code="RATE_LIMIT_EXCEEDED",
                        weight=100,
                        message="Too many requests from this IP in a short time.",
                    )
                ],
                captcha_required=False,
                captcha_verified=False,
                evaluated_at=datetime.now(UTC),
            )

        if challenge.request_ip:
            if not request_ip:
                raise HTTPException(status_code=400, detail="captcha_challenge_ip_missing")
            if challenge.request_ip != request_ip:
                raise HTTPException(
                    status_code=400,
                    detail="captcha_challenge_ip_mismatch",
                )

        if challenge.origin:
            if not origin:
                raise HTTPException(
                    status_code=400,
                    detail="captcha_challenge_origin_missing",
                )
            if challenge.origin.strip().lower() != origin.strip().lower():
                raise HTTPException(
                    status_code=400,
                    detail="captcha_challenge_origin_mismatch",
                )

        verification = await self._turnstile_verifier.verify(
            token=payload.captcha_token,
            remote_ip=request_ip,
        )

        if verification.success:
            consumed = await self._captcha_challenges.consume(payload.challenge_id)
            if not consumed:
                raise HTTPException(status_code=404, detail="captcha_challenge_not_found")

            base = consumed.response
            response = FraudCheckResponse(
                decision="allow",
                risk_score=base.risk_score,
                fingerprint_id=base.fingerprint_id,
                request_ip=request_ip,
                ip_country_iso=base.ip_country_iso,
                signals=base.signals,
                captcha_required=False,
                captcha_verified=True,
                captcha_provider=self._turnstile_verifier.provider,
                captcha_site_key=self._turnstile_verifier.site_key,
                captcha_error_codes=[],
                challenge_id=payload.challenge_id,
                evaluated_at=datetime.now(UTC),
            )
            await self._save_log(response=response, origin=origin)
            return response

        await self._captcha_challenges.increment_attempts(payload.challenge_id)
        base = challenge.response
        response = FraudCheckResponse(
            decision=base.decision,
            risk_score=base.risk_score,
            fingerprint_id=base.fingerprint_id,
            request_ip=request_ip,
            ip_country_iso=base.ip_country_iso,
            signals=base.signals,
            captcha_required=True,
            captcha_verified=False,
            captcha_provider=self._turnstile_verifier.provider,
            captcha_site_key=self._turnstile_verifier.site_key,
            captcha_error_codes=verification.error_codes,
            challenge_id=payload.challenge_id,
            evaluated_at=datetime.now(UTC),
        )
        await self._save_log(response=response, origin=origin)
        return response
