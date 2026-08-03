"""Bearer-protected live read boundary for A-028 Palace Vitals."""

from fastapi import APIRouter, Request

from spine.problems import ProblemJSONResponse, problem_openapi, problem_response
from spine.vitals.contracts import VitalsSnapshot
from spine.vitals.service import VitalsService

router = APIRouter(tags=["vitals"])


@router.get(
    "/v1/vitals",
    response_model=VitalsSnapshot,
    responses={
        401: problem_openapi("Bearer token missing or invalid"),
        422: problem_openapi("Query parameters are not accepted"),
        500: problem_openapi("Unexpected service failure"),
    },
)
async def get_vitals(request: Request) -> VitalsSnapshot | ProblemJSONResponse:
    if request.query_params:
        return problem_response(
            status=422,
            title="Unprocessable Content",
            detail="GET /v1/vitals does not accept query parameters.",
            instance=request.url.path,
            endpoint=f"{request.method} {request.url.path}",
        )
    return await _service(request).snapshot()


def _service(request: Request) -> VitalsService:
    return request.app.state.vitals_service


__all__ = ["router"]
