from functools import lru_cache
from typing import Literal, final

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class APIConfig(BaseModel):
    title: str = "Fraud Checker API"
    version: str = "1.0.0"
    port: int = 8000
    host: str = "0.0.0.0"
    allowed_hosts: list[str] = ["*"]


class FraudConfig(BaseModel):
    block_score_threshold: int = 70
    review_score_threshold: int = 40

    trust_forwarded_ip: bool = False

    rate_limit_window_seconds: int = 60
    rate_limit_max_requests_per_ip: int = 120

    ip_geolocation_enabled: bool = False
    ip_geolocation_timeout_seconds: float = 1.5
    ip_geolocation_base_url: str = "https://ipapi.co"
    ip_geolocation_cache_ttl_seconds: int = 300

    # Optional captcha challenge for suspicious traffic.
    captcha_enabled: bool = False
    captcha_provider: Literal["turnstile", "hcaptcha", "recaptcha"] = "turnstile"
    captcha_site_key: str | None = None
    captcha_secret_key: str | None = None
    captcha_timeout_seconds: float = 2.0
    captcha_verify_url: str | None = None
    captcha_challenge_ttl_seconds: int = 600  # 10 minutes


@final
class Config(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP__",
        env_nested_delimiter="__",
        extra="ignore",
    )

    env: Literal["local", "dev", "prod"] = "local"

    api: APIConfig = APIConfig()
    fraud: FraudConfig = FraudConfig()


@lru_cache
def get_config() -> Config:
    return Config()
