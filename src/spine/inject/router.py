"""HTTP boundary for the SPEC C.4 injection and feedback endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field

from spine.contracts import (
    CommitResponse,
    ContractRequest,
    FeedbackResponse,
    PrepareResponse,
)
from spine.embeddings import EmbeddingProviderError
from spine.inject.service import (
    PrepareCommand,
    PrepareConflictError,
    PrepareService,
    ThreadAlreadyPreparedError,
    ThreadIdentityConflictError,
)
from spine.problems import (
    ProblemJSONResponse,
    not_implemented,
    problem_openapi,
    problem_response,
)

router = APIRouter(tags=["injection"])

ERROR_RESPONSES = {
    401: problem_openapi("Bearer token missing or invalid"),
    422: problem_openapi("Request does not match the endpoint contract"),
    500: problem_openapi("Unexpected service failure"),
}

STUB_RESPONSES = ERROR_RESPONSES | {
    501: problem_openapi("Agent Zero contract stub"),
}

PREPARE_RESPONSES = ERROR_RESPONSES | {
    409: problem_openapi("Thread identity or snapshot conflict"),
    503: problem_openapi("Embedding provider unavailable"),
}


class PrepareRequest(ContractRequest):
    thread_id: UUID
    agent_id: str
    machine_id: str
    principal_id: str
    project_key: str | None = None
    agent_kind: str | None = None
    prompt: str
    model_context_tokens: Annotated[int, Field(gt=0)]


class RemovedMemory(ContractRequest):
    memory_id: UUID
    reason: Literal["not_relevant", "wrong", "never"]


class CommitRequest(ContractRequest):
    injection_id: UUID
    removed: list[RemovedMemory]
    added_back: list[UUID]


class FeedbackRequest(ContractRequest):
    injection_id: UUID
    memory_id: UUID
    signal: Literal["mid_thread_removed", "cited"]


@router.post(
    "/v1/inject/prepare",
    response_model=PrepareResponse,
    responses=PREPARE_RESPONSES,
)
async def prepare(
    body: PrepareRequest,
    request: Request,
) -> PrepareResponse | ProblemJSONResponse:
    try:
        return await _prepare_service(request).prepare(
            PrepareCommand(
                thread_id=body.thread_id,
                agent_id=body.agent_id,
                machine_id=body.machine_id,
                principal_id=body.principal_id,
                project_key=body.project_key,
                agent_kind=body.agent_kind if body.agent_kind is not None else "general",
                prompt=body.prompt,
                model_context_tokens=body.model_context_tokens,
            )
        )
    except ThreadAlreadyPreparedError:
        return _conflict(
            request,
            "This thread already has its single M1 memory injection.",
        )
    except ThreadIdentityConflictError:
        return _conflict(
            request,
            "The thread ID is already assigned to different request metadata.",
        )
    except PrepareConflictError:
        return _conflict(
            request,
            "Concurrent memory changes prevented a stable prepare snapshot.",
        )
    except EmbeddingProviderError:
        return problem_response(
            status=503,
            title="Service Unavailable",
            detail="The embedding provider could not complete the request.",
            instance=request.url.path,
            endpoint=f"{request.method} {request.url.path}",
        )


@router.post(
    "/v1/inject/commit",
    response_model=CommitResponse,
    responses=STUB_RESPONSES,
)
async def commit(_: CommitRequest, request: Request) -> ProblemJSONResponse:
    return not_implemented("POST /v1/inject/commit", request.url.path)


@router.post(
    "/v1/feedback",
    response_model=FeedbackResponse,
    responses=STUB_RESPONSES,
)
async def feedback(_: FeedbackRequest, request: Request) -> ProblemJSONResponse:
    return not_implemented("POST /v1/feedback", request.url.path)


def _prepare_service(request: Request) -> PrepareService:
    return request.app.state.prepare_service


def _conflict(request: Request, detail: str) -> ProblemJSONResponse:
    return problem_response(
        status=409,
        title="Conflict",
        detail=detail,
        instance=request.url.path,
        endpoint=f"{request.method} {request.url.path}",
    )
