import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from dishka.integrations.fastapi import setup_dishka
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.api import register_routers
from app.api.middleware import ApiKeyMiddleware
from app.ioc import get_async_container
from app.services.logging import setup_logging
from app.settings import get_config

logger = logging.getLogger(__name__)

_OPENAPI_API_KEY_SCHEME = "ApiKeyAuth"


def _install_openapi_api_key_security(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
        )

        components = schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes[_OPENAPI_API_KEY_SCHEME] = {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
        schema["security"] = [{_OPENAPI_API_KEY_SCHEME: []}]

        public_path = schema.get("paths", {}).get("/fraud/collector.js", {})
        for operation in public_path.values():
            operation["security"] = []

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.database.base import Base
    from app.database.engine import engine

    # Import models so Base.metadata knows about them
    import app.api.modules.fraud.models  # noqa: F401

    logger.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Starting application...")
    yield
    logger.info("Shutting down application...")
    await engine.dispose()


def get_production_app() -> FastAPI:
    """Get the FastAPI application instance."""
    config = get_config()
    setup_logging(config.env)

    app = FastAPI(
        title=config.api.title,
        version=config.api.version,
        lifespan=lifespan,
    )

    if config.api.api_key:
        app.add_middleware(ApiKeyMiddleware, api_key=config.api.api_key)
        _install_openapi_api_key_security(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.allowed_hosts,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_router = APIRouter()
    register_routers(api_router)
    app.include_router(api_router)

    setup_dishka(get_async_container(), app)

    return app
