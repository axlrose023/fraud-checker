from dishka import FromDishka
from dishka.integrations.fastapi import DishkaRoute
from fastapi import APIRouter, Request, Response

from app.api.modules.fraud.schema import (
    CaptchaStepUpRequest,
    FraudCheckRequest,
    FraudCheckResponse,
)
from app.api.modules.fraud.service import FraudFacadeService
from app.api.modules.fraud.services.public.collector import build_collector_script

router = APIRouter(route_class=DishkaRoute)


@router.post("/check", response_model=FraudCheckResponse, status_code=200)
async def check_fraud(
    request: Request,
    payload: FraudCheckRequest,
    facade: FromDishka[FraudFacadeService],
) -> FraudCheckResponse:
    return await facade.check_request(request=request, payload=payload)


@router.post("/step-up", response_model=FraudCheckResponse, status_code=200)
async def captcha_step_up(
    request: Request,
    payload: CaptchaStepUpRequest,
    facade: FromDishka[FraudFacadeService],
) -> FraudCheckResponse:
    return await facade.step_up_request(request=request, payload=payload)


@router.get("/collector.js", status_code=200)
async def get_collector_script() -> Response:
    script = build_collector_script()
    return Response(content=script, media_type="application/javascript")
