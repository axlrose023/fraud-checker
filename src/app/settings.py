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
