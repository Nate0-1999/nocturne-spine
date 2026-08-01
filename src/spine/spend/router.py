"""Authenticated HTTP ingestion boundary for M2A receipt batches."""

from fastapi import APIRouter, Request

from spine.problems import ProblemJSONResponse, problem_openapi, problem_response
from spine.spend.contracts import SpendEventsRequest, SpendEventsResponse
from spine.spend.service import SpendEventConflictError, SpendService

router = APIRouter(prefix="/v1/spend", tags=["spend"])


@router.post(
    "/events",
    response_model=SpendEventsResponse,
    responses={
        401: problem_openapi("Bearer token missing or invalid"),
        409: problem_openapi("event_uid conflicts with an existing receipt"),
        422: problem_openapi("Request does not match the endpoint contract"),
        500: problem_openapi("Unexpected service failure"),
    },
)
async def append_spend_events(
    body: SpendEventsRequest,
    request: Request,
) -> SpendEventsResponse | ProblemJSONResponse:
    try:
        accepted = await _service(request).append(body.events)
    except SpendEventConflictError as error:
        return problem_response(
            status=409,
            title="Conflict",
            detail=f"Spend event {error.event_uid} conflicts with its append-only receipt.",
            instance=request.url.path,
            endpoint=f"{request.method} {request.url.path}",
        )
    return SpendEventsResponse(accepted=accepted)


def _service(request: Request) -> SpendService:
    return request.app.state.spend_service


__all__ = ["router"]
