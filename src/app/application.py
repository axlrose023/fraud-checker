import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dishka.integrations.fastapi import setup_dishka
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import register_routers
from app.api.middleware import ApiKeyMiddleware
from app.ioc import get_async_container
from app.services.logging import setup_logging
from app.settings import get_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting application...")
    yield
    logger.info("Shutting down application...")


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
