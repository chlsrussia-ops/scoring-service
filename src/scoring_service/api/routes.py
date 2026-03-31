from __future__ import annotations

from fastapi import APIRouter, Request

from scoring_service.config import Settings
from scoring_service.contracts import ErrorResponse, ScoreRequest, ScoreResponse
from scoring_service.executor import execute_response

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@router.post(
    "/v1/score",
    response_model=ScoreResponse,
    responses={400: {"model": ErrorResponse}},
)
def score(request: ScoreRequest, http_request: Request) -> ScoreResponse:
    settings: Settings = http_request.app.state.settings
    return execute_response(request, settings)
