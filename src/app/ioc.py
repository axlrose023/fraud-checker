from collections.abc import AsyncIterator

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.modules.auth.service import AuthService
from app.api.modules.auth.services import JwtService
from app.api.modules.users.service import UserService
from app.clients.providers import HttpClientsProvider
from app.database.engine import SessionFactory
from app.database.uow import UnitOfWork
from app.settings import Config, get_config


class AppProvider(Provider):
    """Application provider for dependency injection."""

    @provide(scope=Scope.APP)
    def get_config(self) -> Config:
        return get_config()

    @provide(scope=Scope.REQUEST)
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        async with SessionFactory() as session:
            yield session

    @provide(scope=Scope.REQUEST)
    async def get_uow(self, session: AsyncSession) -> AsyncIterator[UnitOfWork]:
        async with UnitOfWork(session) as uow:
            yield uow


class ServicesProvider(Provider):
    """Services provider for dependency injection."""

    @provide(scope=Scope.APP)
    def get_jwt_service(self, config: Config) -> JwtService:
        return JwtService(config)

    @provide(scope=Scope.REQUEST)
    async def get_auth_service(
        self, uow: UnitOfWork, jwt_service: JwtService
    ) -> AuthService:
        return AuthService(uow, jwt_service)

    @provide(scope=Scope.REQUEST)
    async def get_user_service(
        self, uow: UnitOfWork, auth_service: AuthService
    ) -> UserService:
        return UserService(uow, auth_service)


def get_async_container() -> AsyncContainer:
    return make_async_container(
        AppProvider(),
        ServicesProvider(),
        HttpClientsProvider(),
    )
