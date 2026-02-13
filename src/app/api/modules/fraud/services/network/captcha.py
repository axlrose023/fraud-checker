import logging
from dataclasses import dataclass

import httpx

from app.settings import Config

logger = logging.getLogger(__name__)


_DEFAULT_VERIFY_URL: dict[str, str] = {
    "turnstile": "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    "hcaptcha": "https://hcaptcha.com/siteverify",
    "recaptcha": "https://www.google.com/recaptcha/api/siteverify",
}


@dataclass(slots=True)
class CaptchaVerificationResult:
    success: bool
    error_codes: list[str]
    hostname: str | None = None
    action: str | None = None


class CaptchaVerifierService:
    def __init__(self, client: httpx.AsyncClient, config: Config):
        self._client = client

        self._enabled = config.fraud.captcha_enabled
        self._provider = config.fraud.captcha_provider
        self._site_key = config.fraud.captcha_site_key
        self._secret_key = config.fraud.captcha_secret_key
        self._timeout = config.fraud.captcha_timeout_seconds
        self._verify_url = (
            config.fraud.captcha_verify_url or _DEFAULT_VERIFY_URL.get(self._provider)
        )

    @property
    def enabled(self) -> bool:
        return bool(self._enabled)

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def site_key(self) -> str | None:
        return self._site_key

    def is_configured(self) -> bool:
        return bool(self._enabled and self._secret_key and self._site_key and self._verify_url)

    async def verify(
        self,
        token: str,
        remote_ip: str | None,
    ) -> CaptchaVerificationResult:
        if not self.is_configured():
            return CaptchaVerificationResult(
                success=False,
                error_codes=["captcha_not_configured"],
            )

        form: dict[str, str] = {
            "secret": self._secret_key or "",
            "response": token,
        }
        if remote_ip:
            form["remoteip"] = remote_ip
        if self._provider == "hcaptcha" and self._site_key:
            # Optional per hCaptcha docs; helps when multiple sitekeys are used.
            form["sitekey"] = self._site_key

        try:
            response = await self._client.post(
                self._verify_url or "",
                data=form,
                timeout=self._timeout,
                follow_redirects=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Captcha verification request failed",
                extra={"provider": self._provider},
            )
            logger.debug("Captcha verification network error: %s", exc)
            return CaptchaVerificationResult(
                success=False,
                error_codes=["captcha_network_error"],
            )

        try:
            data = response.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Captcha verification returned non-JSON response",
                extra={"provider": self._provider, "status_code": response.status_code},
            )
            logger.debug("Captcha verification JSON decode error: %s", exc)
            return CaptchaVerificationResult(
                success=False,
                error_codes=[f"captcha_http_{response.status_code}"],
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
            codes = [f"captcha_http_{response.status_code}"]

        hostname = data.get("hostname") if isinstance(data.get("hostname"), str) else None
        action = data.get("action") if isinstance(data.get("action"), str) else None

        return CaptchaVerificationResult(
            success=success,
            error_codes=codes,
            hostname=hostname,
            action=action,
        )


__all__ = ("CaptchaVerificationResult", "CaptchaVerifierService")
