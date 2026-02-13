from app.api.modules.fraud.schema import FraudCheckRequest, FraudSignal
from app.api.modules.fraud.services.context.locale import (
    extract_primary_language,
    language_base,
)
from app.api.modules.fraud.services.core import create_signal
from app.api.modules.fraud.services.network.common import normalize_text
from app.api.modules.fraud.services.network.headers_utils import (
    jaccard_similarity,
    normalize_brand,
    parse_accept_language,
    parse_sec_ch_ua_brands,
)
from app.api.modules.fraud.services.network.user_agent import is_chromium_ua


class HeaderConsistencyService:
    def collect(
        self,
        payload: FraudCheckRequest,
        headers: dict[str, str],
    ) -> list[FraudSignal]:
        signals: list[FraudSignal] = []

        header_ua = headers.get("user-agent")
        if header_ua and normalize_text(header_ua) != normalize_text(
            payload.navigator.user_agent
        ):
            signals.append(
                create_signal(
                    code="UA_HEADER_PAYLOAD_MISMATCH",
                    weight=40,
                    message="Request User-Agent does not match payload user_agent.",
                )
            )

        header_accept_language = headers.get("accept-language")
        payload_language = payload.navigator.language
        if header_accept_language and payload_language:
            primary_header_language = extract_primary_language(header_accept_language)
            if primary_header_language and language_base(primary_header_language) != language_base(
                payload_language
            ):
                signals.append(
                    create_signal(
                        code="ACCEPT_LANGUAGE_MISMATCH",
                        weight=15,
                        message="Request Accept-Language does not match payload language.",
                    )
                )

        if header_accept_language and payload.navigator.languages:
            header_languages = parse_accept_language(header_accept_language)
            header_bases = {language_base(item) for item in header_languages}
            payload_bases = {language_base(item) for item in payload.navigator.languages}
            if header_bases and payload_bases and not (header_bases & payload_bases):
                signals.append(
                    create_signal(
                        code="ACCEPT_LANGUAGE_LIST_MISMATCH",
                        weight=8,
                        message="Accept-Language header is inconsistent with navigator.languages.",
                    )
                )

        if payload.client_hints and payload.client_hints.mobile is not None:
            header_mobile = headers.get("sec-ch-ua-mobile")
            if header_mobile in {"?0", "?1"}:
                is_header_mobile = header_mobile == "?1"
                if is_header_mobile != payload.client_hints.mobile:
                    signals.append(
                        create_signal(
                            code="CH_MOBILE_MISMATCH",
                            weight=20,
                            message=(
                                "sec-ch-ua-mobile header does not match payload client hints."
                            ),
                        )
                    )

        if payload.client_hints and payload.client_hints.platform:
            header_platform = headers.get("sec-ch-ua-platform")
            if header_platform:
                normalized_header_platform = normalize_text(
                    header_platform.strip().strip('"')
                )
                normalized_payload_platform = normalize_text(payload.client_hints.platform)
                if normalized_header_platform != normalized_payload_platform:
                    signals.append(
                        create_signal(
                            code="CH_PLATFORM_MISMATCH",
                            weight=15,
                            message=(
                                "sec-ch-ua-platform header does not match payload client hints."
                            ),
                        )
                    )

        header_ch_ua = headers.get("sec-ch-ua")
        if payload.client_hints and payload.client_hints.brands:
            payload_brands = {
                normalize_brand(item) for item in payload.client_hints.brands if item
            }
            header_brands = {
                normalize_brand(item) for item in parse_sec_ch_ua_brands(header_ch_ua)
            }

            if payload_brands and header_brands:
                similarity = jaccard_similarity(payload_brands, header_brands)
                if similarity < 0.5:
                    signals.append(
                        create_signal(
                            code="CH_BRANDS_MISMATCH",
                            weight=25,
                            message="sec-ch-ua brands do not match payload client hints brands.",
                        )
                    )
                elif similarity < 1.0:
                    signals.append(
                        create_signal(
                            code="CH_BRANDS_PARTIAL_MISMATCH",
                            weight=10,
                            message="sec-ch-ua brands partially mismatch payload client hints brands.",
                        )
                    )

        ua = payload.navigator.user_agent.lower()
        if is_chromium_ua(ua) and not header_ch_ua and payload.client_hints is not None:
            signals.append(
                create_signal(
                    code="CH_HEADERS_MISSING",
                    weight=8,
                    message="User-AgentData is present but sec-ch-ua headers are missing.",
                )
            )

        return signals


__all__ = ("HeaderConsistencyService",)
