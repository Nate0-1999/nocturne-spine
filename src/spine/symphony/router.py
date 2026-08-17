"""Bearer-protected HTTP boundary for A-059 Symphony memory state."""

from fastapi import APIRouter, Request

from spine.contracts import ULID
from spine.memory.service import MemoryValidationError, StagedMemoryConflictError
from spine.problems import ProblemJSONResponse, problem_openapi, problem_response
from spine.symphony.contracts import (
    ResolveRunRequest,
    ResolveRunResponse,
    StageMemoryRequest,
    StageMemoryResponse,
    VisibilityRequest,
    VisibilityResponse,
)
from spine.symphony.service import SymphonyConflictError, SymphonyNotFoundError

router = APIRouter(tags=["symphony-memory"])
ERRORS = {
    401: problem_openapi("Bearer token missing or invalid"),
    409: problem_openapi("Symphony lineage conflict"),
    422: problem_openapi("Invalid Symphony memory request"),
}


@router.post(
    "/v1/symphony/memories",
    response_model=StageMemoryResponse,
    status_code=201,
    responses=ERRORS,
)
async def stage_memory(
    body: StageMemoryRequest, request: Request
) -> StageMemoryResponse | ProblemJSONResponse:
    try:
        return await request.app.state.symphony_service.stage(body)
    except StagedMemoryConflictError as exc:
        return _problem(request, 409, str(exc))
    except MemoryValidationError as exc:
        return _problem(request, 422, str(exc))


@router.post(
    "/v1/symphony/memories/query",
    response_model=VisibilityResponse,
    responses=ERRORS,
)
async def visible_memories(body: VisibilityRequest, request: Request) -> VisibilityResponse:
    return await request.app.state.symphony_service.visible(body)


@router.post(
    "/v1/symphony/runs/{run_id}/resolve",
    response_model=ResolveRunResponse,
    responses=ERRORS | {404: problem_openapi("Staged run or winner missing")},
)
async def resolve_run(
    run_id: ULID, body: ResolveRunRequest, request: Request
) -> ResolveRunResponse | ProblemJSONResponse:
    try:
        return await request.app.state.symphony_service.resolve(run_id, body)
    except SymphonyNotFoundError as exc:
        return _problem(request, 404, str(exc))
    except SymphonyConflictError as exc:
        return _problem(request, 409, str(exc))


def _problem(request: Request, status: int, detail: str) -> ProblemJSONResponse:
    return problem_response(
        status=status,
        title={404: "Not Found", 409: "Conflict"}.get(status, "Unprocessable Content"),
        detail=detail,
        instance=request.url.path,
        endpoint=f"{request.method} {request.url.path}",
    )
