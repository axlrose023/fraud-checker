
MOBILE_UA_MARKERS = ("android", "iphone", "ipad", "ipod", "mobile")
AUTOMATION_MARKERS = (
    "headless",
    "phantomjs",
    "puppeteer",
    "playwright",
    "selenium",
    "webdriver",
)
BOT_UA_MARKERS = ("bot", "crawler", "spider", "scrapy", "curl", "wget")
STRONG_BOT_UA_MARKERS = (
    "curl/",
    "wget/",
    "python-requests",
    "go-http-client",
    "httpclient",
)


def contains_any(value: str, markers: tuple[str, ...]) -> bool:
    return any(marker in value for marker in markers)


def has_mobile_ua(ua: str) -> bool:
    return contains_any(ua, MOBILE_UA_MARKERS)


def is_android_ua(ua: str) -> bool:
    return "android" in ua


def is_ios_ua(ua: str) -> bool:
    return "iphone" in ua or "ipad" in ua or "ipod" in ua


def is_desktop_mac_ua(ua: str) -> bool:
    return "macintosh" in ua


def is_chromium_ua(ua: str) -> bool:
    return any(token in ua for token in ("chrome/", "chromium", "crios", "edg/", "opr/"))


def is_tablet_ua(ua: str) -> bool:
    if "ipad" in ua or "tablet" in ua:
        return True
    return "android" in ua and "mobile" not in ua


__all__ = (
    "AUTOMATION_MARKERS",
    "BOT_UA_MARKERS",
    "MOBILE_UA_MARKERS",
    "STRONG_BOT_UA_MARKERS",
    "contains_any",
    "has_mobile_ua",
    "is_android_ua",
    "is_chromium_ua",
    "is_desktop_mac_ua",
    "is_ios_ua",
    "is_tablet_ua",
)
