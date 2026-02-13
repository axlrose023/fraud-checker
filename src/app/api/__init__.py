from fastapi import APIRouter


def register_routers(router: APIRouter) -> None:
    from app.api.modules.fraud.routes import router as fraud_router

    router.include_router(fraud_router, prefix="/fraud", tags=["Fraud"])
