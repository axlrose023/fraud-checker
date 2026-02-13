import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_EXEMPT_PATHS = frozenset({"/fraud/collector.js", "/openapi.json", "/docs", "/redoc"})


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str) -> None:  # noqa: ANN001
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next) -> Response:  # noqa: ANN001
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if not hmac.compare_digest(provided, self._api_key):
            return JSONResponse(
                {"detail": "Invalid or missing API key"},
                status_code=401,
            )

        return await call_next(request)
