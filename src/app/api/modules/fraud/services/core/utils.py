import json
from hashlib import sha256

from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal


def create_signal(code: str, weight: int, message: str) -> FraudSignal:
    return FraudSignal(
        code=code,
        severity=severity_for_weight(weight),
        weight=weight,
        message=message,
    )


def severity_for_weight(weight: int) -> str:
    if weight >= 30:
        return "high"
    if weight >= 12:
        return "medium"
    return "low"


def decision_for_score(
    score: int,
    block_score_threshold: int,
    review_score_threshold: int,
) -> str:
    if score >= block_score_threshold:
        return "block"
    if score >= review_score_threshold:
        return "review"
    return "allow"


def build_fingerprint(payload: FraudCheckRequest) -> str:
    snapshot = {
        "ua": payload.navigator.user_agent,
        "platform": payload.navigator.platform,
        "language": payload.navigator.language,
        "languages": payload.navigator.languages,
        "screen": payload.screen.model_dump(mode="json"),
        "viewport": payload.viewport.model_dump(mode="json"),
        "webgl": payload.webgl.model_dump(mode="json") if payload.webgl else None,
        "hints": (
            payload.client_hints.model_dump(mode="json") if payload.client_hints else None
        ),
    }
    body = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(body).hexdigest()[:24]


__all__ = (
    "build_fingerprint",
    "create_signal",
    "decision_for_score",
    "severity_for_weight",
)
