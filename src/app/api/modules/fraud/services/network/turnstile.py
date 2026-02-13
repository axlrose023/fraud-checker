import logging
from dataclasses import dataclass

import httpx

from app.settings import Config

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TurnstileVerificationResult:
    success: bool
    error_codes: list[str]
    hostname: str | None = None
    action: str | None = None


class TurnstileVerifierService:
    def __init__(self, client: httpx.AsyncClient, config: Config):
        self._client = client
        self._site_key = config.fraud.turnstile_site_key
        self._secret_key = config.fraud.turnstile_secret_key
        self._verify_url = config.fraud.turnstile_verify_url
        self._timeout = config.fraud.turnstile_timeout_seconds

    @property
    def provider(self) -> str:
        return "turnstile"

    @property
    def site_key(self) -> str | None:
        return self._site_key

    def is_configured(self) -> bool:
        return bool(self._site_key and self._secret_key)

    async def verify(
        self,
        token: str,
        remote_ip: str | None,
    ) -> TurnstileVerificationResult:
        if not self.is_configured():
            return TurnstileVerificationResult(
                success=False,
                error_codes=["turnstile_not_configured"],
            )

        form: dict[str, str] = {
            "secret": self._secret_key or "",
            "response": token,
        }
        if remote_ip:
            form["remoteip"] = remote_ip

        try:
            response = await self._client.post(
                self._verify_url,
                data=form,
                timeout=self._timeout,
                follow_redirects=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Turnstile verification request failed")
            logger.debug("Turnstile verification network error: %s", exc)
            return TurnstileVerificationResult(
                success=False,
                error_codes=["turnstile_network_error"],
            )

        try:
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Turnstile verification returned non-JSON response",
                extra={"status_code": response.status_code},
            )
            logger.debug("Turnstile verification JSON decode error: %s", exc)
            return TurnstileVerificationResult(
                success=False,
                error_codes=[f"turnstile_http_{response.status_code}"],
            )

        success = bool(data.get("success"))
        raw_codes = data.get("error-codes") or data.get("error_codes") or []
        if isinstance(raw_codes, str):
            codes = [raw_codes]
        elif isinstance(raw_codes, list):
            codes = [str(item) for item in raw_codes if item]
        else:
            codes = []

        if not success and not codes and response.status_code != 200:
            codes = [f"turnstile_http_{response.status_code}"]

        hostname = data.get("hostname") if isinstance(data.get("hostname"), str) else None
        action = data.get("action") if isinstance(data.get("action"), str) else None

        return TurnstileVerificationResult(
            success=success,
            error_codes=codes,
            hostname=hostname,
            action=action,
        )


__all__ = ("TurnstileVerificationResult", "TurnstileVerifierService")

