"""HTTP boundary for the M2H approval queue."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from spine.problems import ProblemJSONResponse, problem_openapi, problem_response
from spine.queue.contracts import (
    ExtractionRequest,
    ExtractionResponse,
    QueueDecisionRequest,
    QueueDecisionResponse,
    QueueResponse,
)
from spine.queue.service import QueueConflictError, QueueNotFoundError, QueueValidationError

router = APIRouter(tags=["approval-queue"])
ERRORS = {
    401: problem_openapi("Bearer token missing or invalid"),
    422: problem_openapi("Invalid queue request"),
}


@router.post("/v1/extractions", response_model=ExtractionResponse, responses=ERRORS)
async def extract(
    body: ExtractionRequest, request: Request
) -> ExtractionResponse | ProblemJSONResponse:
    try:
        return await request.app.state.queue_service.extract(body)
    except QueueValidationError as exc:
        return _problem(request, 422, str(exc))


@router.get("/v1/approval-queue", response_model=QueueResponse, responses=ERRORS)
async def queue(
    request: Request,
    principal_id: str = Query(min_length=1),
    thread_id: UUID | None = None,
) -> QueueResponse:
    return await request.app.state.queue_service.list_pending(principal_id, thread_id)


@router.post(
    "/v1/approval-queue/{item_uid}/decisions",
    response_model=QueueDecisionResponse,
    responses=ERRORS
    | {404: problem_openapi("Queue item missing"), 409: problem_openapi("Queue item conflict")},
)
async def decide(
    item_uid: str, body: QueueDecisionRequest, request: Request
) -> QueueDecisionResponse | ProblemJSONResponse:
    try:
        return await request.app.state.queue_service.decide(item_uid, body)
    except QueueNotFoundError:
        return _problem(request, 404, "Queue item does not exist.")
    except QueueConflictError as exc:
        return _problem(request, 409, str(exc))
    except QueueValidationError as exc:
        return _problem(request, 422, str(exc))


def _problem(request: Request, status: int, detail: str) -> ProblemJSONResponse:
    return problem_response(
        status=status,
        title={404: "Not Found", 409: "Conflict"}.get(status, "Unprocessable Content"),
        detail=detail,
        instance=request.url.path,
        endpoint=f"{request.method} {request.url.path}",
    )
