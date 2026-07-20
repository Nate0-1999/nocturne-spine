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
from spine.inject.decisions import (
    CommitCommand,
    DecisionService,
    FeedbackCommand,
    InjectionNotFoundError,
    InvalidCommitChoicesError,
    OutcomeConflictError,
    RemovedDecision,
)
from spine.inject.service import (
    PrepareCommand,
    PrepareConflictError,
    PrepareService,
    ThreadAlreadyPreparedError,
    ThreadIdentityConflictError,
)
from spine.problems import (
    ProblemJSONResponse,
    problem_openapi,
    problem_response,
)

router = APIRouter(tags=["injection"])

ERROR_RESPONSES = {
    401: problem_openapi("Bearer token missing or invalid"),
    422: problem_openapi("Request does not match the endpoint contract"),
    500: problem_openapi("Unexpected service failure"),
}

PREPARE_RESPONSES = ERROR_RESPONSES | {
    409: problem_openapi("Thread identity or snapshot conflict"),
    503: problem_openapi("Embedding provider unavailable"),
}

DECISION_RESPONSES = ERROR_RESPONSES | {
    404: problem_openapi("Injection event membership does not exist"),
    409: problem_openapi("Injection outcome conflicts with the request"),
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
    responses=DECISION_RESPONSES,
)
async def commit(
    body: CommitRequest,
    request: Request,
) -> CommitResponse | ProblemJSONResponse:
    try:
        return await _decision_service(request).commit(
            CommitCommand(
                injection_id=body.injection_id,
                removed=tuple(
                    RemovedDecision(memory_id=item.memory_id, reason=item.reason)
                    for item in body.removed
                ),
                added_back=tuple(body.added_back),
            )
        )
    except InjectionNotFoundError as error:
        return _decision_problem(request, 404, "Not Found", str(error))
    except InvalidCommitChoicesError as error:
        return _decision_problem(request, 422, "Unprocessable Content", str(error))
    except OutcomeConflictError as error:
        return _decision_problem(request, 409, "Conflict", str(error))


@router.post(
    "/v1/feedback",
    response_model=FeedbackResponse,
    responses=DECISION_RESPONSES,
)
async def feedback(
    body: FeedbackRequest,
    request: Request,
) -> FeedbackResponse | ProblemJSONResponse:
    try:
        return await _decision_service(request).feedback(
            FeedbackCommand(
                injection_id=body.injection_id,
                memory_id=body.memory_id,
                signal=body.signal,
            )
        )
    except InjectionNotFoundError as error:
        return _decision_problem(request, 404, "Not Found", str(error))
    except OutcomeConflictError as error:
        return _decision_problem(request, 409, "Conflict", str(error))


def _prepare_service(request: Request) -> PrepareService:
    return request.app.state.prepare_service


def _decision_service(request: Request) -> DecisionService:
    return request.app.state.decision_service


def _conflict(request: Request, detail: str) -> ProblemJSONResponse:
    return problem_response(
        status=409,
        title="Conflict",
        detail=detail,
        instance=request.url.path,
        endpoint=f"{request.method} {request.url.path}",
    )


def _decision_problem(
    request: Request,
    status: int,
    title: str,
    detail: str,
) -> ProblemJSONResponse:
    return problem_response(
        status=status,
        title=title,
        detail=detail,
        instance=request.url.path,
        endpoint=f"{request.method} {request.url.path}",
    )
