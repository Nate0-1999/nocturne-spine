"""Authenticated manual trigger for M2F batch proposals."""

from fastapi import APIRouter, Request

from spine.learner.contracts import RetrainResponse
from spine.learner.service import LearnerService
from spine.problems import problem_openapi

router = APIRouter(tags=["learner"])


@router.post(
    "/retrain",
    response_model=RetrainResponse,
    responses={
        401: problem_openapi("Bearer token missing or invalid"),
        500: problem_openapi("Training evidence is invalid or retraining failed"),
    },
)
async def retrain(request: Request) -> RetrainResponse:
    return await _service(request).retrain()


def _service(request: Request) -> LearnerService:
    return request.app.state.learner_service


__all__ = ["router"]
