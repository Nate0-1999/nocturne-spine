"""Bearer-protected transcript resurrection routes."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from spine.problems import ProblemJSONResponse, problem_openapi, problem_response
from spine.transcripts.contracts import (
    AppendTranscriptsRequest,
    TranscriptAppendResult,
    TranscriptList,
    TranscriptStatus,
)
from spine.transcripts.service import TranscriptConflict, TranscriptService

router = APIRouter(tags=["transcripts"])
_RESPONSES = {
    401: problem_openapi("Bearer token missing or invalid"),
    409: problem_openapi("Append disagrees with the immutable transcript prefix"),
    422: problem_openapi("Request does not match the endpoint contract"),
}
Principal = Annotated[str, Query(min_length=1, pattern=r"^\S(?:.*\S)?$")]


@router.post("/v1/transcripts", response_model=TranscriptAppendResult, responses=_RESPONSES)
async def append_transcripts(
    body: AppendTranscriptsRequest, request: Request
) -> TranscriptAppendResult | ProblemJSONResponse:
    try:
        return await _service(request).append(body)
    except TranscriptConflict as error:
        return problem_response(
            status=409,
            title="Conflict",
            detail=f"Transcript append refused: {error}.",
            instance=request.url.path,
            endpoint=f"{request.method} {request.url.path}",
        )


@router.get("/v1/transcripts", response_model=TranscriptList, responses=_RESPONSES)
async def list_transcripts(principal_id: Principal, request: Request) -> TranscriptList:
    return await _service(request).list(principal_id)


@router.get("/v1/transcripts/status", response_model=TranscriptStatus, responses=_RESPONSES)
async def transcript_status(principal_id: Principal, request: Request) -> TranscriptStatus:
    return await _service(request).status(principal_id)


def _service(request: Request) -> TranscriptService:
    return request.app.state.transcript_service


__all__ = ["router"]
