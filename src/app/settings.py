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
    api_key: str | None = None


class PostgresConfig(BaseModel):
    user: str = "postgres"
    password: str = "postgres"
    host: str = "localhost"
    port: int = 5432
    db: str = "fraud_checker"


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

    # Optional Turnstile captcha challenge for suspicious traffic.
    turnstile_site_key: str | None = None
    turnstile_secret_key: str | None = None
    turnstile_verify_url: str = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    turnstile_js_url: str = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
    turnstile_timeout_seconds: float = 2.0
    turnstile_challenge_ttl_seconds: int = 600  # 10 minutes


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
    postgres: PostgresConfig = PostgresConfig()

    @property
    def database_url(self) -> str:
        p = self.postgres
        host = "localhost" if self.env == "local" else p.host
        return (
            f"postgresql+asyncpg://{p.user}:{p.password}@{host}:{p.port}/{p.db}"
        )


@lru_cache
def get_config() -> Config:
    return Config()
