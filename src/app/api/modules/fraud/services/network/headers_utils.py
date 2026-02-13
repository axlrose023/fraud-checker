import re

_SEC_CH_UA_BRAND_RE = re.compile(
    r"\"(?P<brand>[^\"]+)\"\s*;\s*v\s*=\s*\"?(?P<ver>\d+)\"?"
)


def parse_sec_ch_ua_brands(value: str | None) -> set[str]:
    if not value:
        return set()
    return {match.group("brand").strip() for match in _SEC_CH_UA_BRAND_RE.finditer(value)}


def normalize_brand(value: str) -> str:
    return " ".join(value.strip().lower().split())


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def parse_accept_language(header: str | None) -> list[str]:
    if not header:
        return []
    tokens = header.split(",")
    languages: list[str] = []
    for token in tokens:
        value = token.strip()
        if not value:
            continue
        language = value.split(";", 1)[0].strip()
        if language:
            languages.append(language)
    return languages


__all__ = (
    "jaccard_similarity",
    "normalize_brand",
    "parse_accept_language",
    "parse_sec_ch_ua_brands",
)
