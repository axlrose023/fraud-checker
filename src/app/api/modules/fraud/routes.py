from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Query, Request, Response

from app.api.common.utils import build_filters
from app.api.modules.fraud.models import FraudCheckLog
from app.api.modules.fraud.schema import (
    CaptchaVerifyRequest,
    FraudCheckLogListResponse,
    FraudCheckLogPaginationParams,
    FraudCheckLogResponse,
    FraudCheckRequest,
    FraudCheckResponse,
)
from app.api.modules.fraud.service import FraudFacadeService
from app.api.modules.fraud.services.public.collector import build_collector_script
from app.database.uow import UnitOfWork
from app.settings import Config

router = APIRouter(route_class=DishkaRoute)


@router.post("/check", response_model=FraudCheckResponse, status_code=200)
async def check_fraud(
    request: Request,
    payload: FraudCheckRequest,
    facade: FromDishka[FraudFacadeService],
) -> FraudCheckResponse:
    return await facade.check_request(request=request, payload=payload)


@router.post("/captcha/verify", response_model=FraudCheckResponse, status_code=200)
async def verify_captcha(
    request: Request,
    payload: CaptchaVerifyRequest,
    facade: FromDishka[FraudFacadeService],
) -> FraudCheckResponse:
    return await facade.verify_captcha_request(request=request, payload=payload)


@router.get("/collector.js", status_code=200)
async def get_collector_script(config: FromDishka[Config]) -> Response:
    script = build_collector_script(
        turnstile_js_url=config.fraud.turnstile_js_url,
    )
    return Response(content=script, media_type="application/javascript")


@router.get("/logs", response_model=FraudCheckLogListResponse, status_code=200)
async def get_fraud_logs(
    uow: FromDishka[UnitOfWork],
    params: FraudCheckLogPaginationParams = Query(),
) -> FraudCheckLogListResponse:
    filter_data = params.model_dump(
        exclude={"page", "page_size"},
        exclude_none=True,
    )
    filters = build_filters(FraudCheckLog, filter_data)

    items = await uow.fraud_logs.get_all(
        limit=params.page_size,
        offset=params.offset,
        filters=filters,
    )
    total = await uow.fraud_logs.get_total_count(filters)

    return FraudCheckLogListResponse(
        items=[FraudCheckLogResponse.model_validate(item) for item in items],
        total=total,
        page=params.page,
        page_size=params.page_size,
    )
