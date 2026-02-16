from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, DateTimeMixin


class FraudCheckLog(Base, DateTimeMixin):
    __tablename__ = "fraud_check_logs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    request_ip: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    ip_country_iso: Mapped[str | None] = mapped_column(
        String(2), nullable=True
    )
    fingerprint_id: Mapped[str] = mapped_column(String(128), index=True)
    origin: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str] = mapped_column(String(16), index=True)
    risk_score: Mapped[int] = mapped_column(Integer, index=True)
    signals: Mapped[list] = mapped_column(JSON, default=list)
    captcha_required: Mapped[bool] = mapped_column(Boolean, default=False)
    captcha_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    challenge_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
