"""HTTP clients provider for dependency injection."""

from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, provide

from app.api.modules.fraud.services.network import IpGeoClient, TurnstileVerifierService
from app.settings import Config


class HttpClientsProvider(Provider):
    """Provider for HTTP clients and external service integrations.

    This provider manages the lifecycle of httpx.AsyncClient and provides
    HTTP clients for external services with proper dependency injection.

    Key features:
    - Single httpx.AsyncClient instance per APP scope (connection pooling)
    - Automatic client cleanup on application shutdown
    - Easy integration with custom service clients
    - Configuration injection from Config

    Usage:
        Add this provider to your IoC container in ioc.py:

        def get_async_container() -> AsyncContainer:
            return make_async_container(
                AppProvider(),
                ServicesProvider(),
                HttpClientsProvider(),  # Add this
            )
    """

    @provide(scope=Scope.APP)
    async def get_httpx_client(self) -> AsyncIterator[httpx.AsyncClient]:
        """Provide httpx AsyncClient with connection pooling.

        Scope: APP - single instance for the entire application lifecycle.
        This enables connection pooling and resource reuse.

        Default configuration:
        - timeout: 30 seconds
        - connection limits: 100 total, 20 per host
        - http2: enabled
        - follow_redirects: enabled

        :return: Configured httpx AsyncClient instance
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True,
        ) as client:
            yield client

    @provide(scope=Scope.APP)
    def get_ip_geo_client(
        self,
        client: httpx.AsyncClient,
        config: Config,
    ) -> IpGeoClient:
        return IpGeoClient(client, config)

    @provide(scope=Scope.APP)
    def get_turnstile_verifier(
        self,
        client: httpx.AsyncClient,
        config: Config,
    ) -> TurnstileVerifierService:
        return TurnstileVerifierService(client, config)

    # Add more client providers here as needed:
    #
    # @provide(scope=Scope.REQUEST)
    # def get_another_service_client(
    #     self,
    #     client: httpx.AsyncClient,
    #     config: Config,
    # ) -> AnotherServiceClient:
    #     return AnotherServiceClient(client, config)
