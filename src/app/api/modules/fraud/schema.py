from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NavigatorSignals(BaseModel):
    user_agent: str = Field(..., min_length=10, max_length=2048)
    language: str | None = Field(default=None, max_length=32)
    languages: list[str] = Field(default_factory=list, max_length=20)
    platform: str | None = Field(default=None, max_length=128)
    webdriver: bool | None = None
    hardware_concurrency: int | None = Field(default=None, ge=1, le=256)
    device_memory: float | None = Field(default=None, ge=0.25, le=128)
    max_touch_points: int | None = Field(default=None, ge=0, le=64)
    cookie_enabled: bool | None = None
    plugins_count: int | None = Field(default=None, ge=0, le=200)

    model_config = ConfigDict(extra="forbid")


class ScreenSignals(BaseModel):
    width: int = Field(..., ge=1, le=10000)
    height: int = Field(..., ge=1, le=10000)
    avail_width: int | None = Field(default=None, ge=1, le=10000)
    avail_height: int | None = Field(default=None, ge=1, le=10000)
    color_depth: int | None = Field(default=None, ge=1, le=64)
    pixel_ratio: float | None = Field(default=None, ge=0.1, le=10)

    model_config = ConfigDict(extra="forbid")


class ViewportSignals(BaseModel):
    width: int = Field(..., ge=1, le=10000)
    height: int = Field(..., ge=1, le=10000)

    model_config = ConfigDict(extra="forbid")


class WebGLSignals(BaseModel):
    vendor: str | None = Field(default=None, max_length=256)
    renderer: str | None = Field(default=None, max_length=512)

    model_config = ConfigDict(extra="forbid")


class LocationSignals(BaseModel):
    country_iso: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    timezone: str | None = Field(default=None, max_length=128)
    utc_offset_minutes: int | None = Field(default=None, ge=-840, le=840)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    accuracy_meters: float | None = Field(default=None, ge=0, le=50000)

    model_config = ConfigDict(extra="forbid")


class ClientHintsSignals(BaseModel):
    mobile: bool | None = None
    platform: str | None = Field(default=None, max_length=64)
    brands: list[str] = Field(default_factory=list, max_length=20)

    model_config = ConfigDict(extra="forbid")


class BehaviorSignals(BaseModel):
    time_on_page_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    max_scroll_y: int | None = Field(default=None, ge=0, le=100_000)
    scroll_count: int | None = Field(default=None, ge=0, le=100_000)
    document_height: int | None = Field(default=None, ge=0, le=100_000)
    keydown_count: int | None = Field(default=None, ge=0, le=100_000)
    mouse_move_count: int | None = Field(default=None, ge=0, le=1_000_000)
    touch_count: int | None = Field(default=None, ge=0, le=100_000)

    model_config = ConfigDict(extra="forbid")


class FraudCheckRequest(BaseModel):
    event_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    client_reported_ip: str | None = Field(default=None, max_length=64)
    navigator: NavigatorSignals
    screen: ScreenSignals
    viewport: ViewportSignals
    webgl: WebGLSignals | None = None
    location: LocationSignals | None = None
    client_hints: ClientHintsSignals | None = None
    behavior: BehaviorSignals | None = None
    collected_at: datetime | None = None

    model_config = ConfigDict(extra="forbid")


class CaptchaVerifyRequest(BaseModel):
    challenge_id: str = Field(..., min_length=16, max_length=256)
    captcha_token: str = Field(..., min_length=16, max_length=8192)

    model_config = ConfigDict(extra="forbid")


class FraudSignal(BaseModel):
    code: str
    severity: Literal["low", "medium", "high"]
    weight: int = Field(..., ge=1, le=100)
    message: str


class FraudCheckResponse(BaseModel):
    decision: Literal["allow", "review", "block"]
    risk_score: int = Field(..., ge=0, le=100)
    fingerprint_id: str
    request_ip: str | None = None
    ip_country_iso: str | None = None
    signals: list[FraudSignal]

    captcha_required: bool = False
    captcha_verified: bool = False
    captcha_provider: str | None = None
    captcha_site_key: str | None = None
    captcha_error_codes: list[str] = Field(default_factory=list, max_length=50)
    challenge_id: str | None = None

    evaluated_at: datetime
