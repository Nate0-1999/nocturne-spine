"""P0 stubs for the injection and feedback endpoints in SPEC C.4."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request

from spine.contracts import ContractRequest
from spine.problems import ProblemJSONResponse, not_implemented, problem_openapi

router = APIRouter(tags=["injection"])

STUB_RESPONSES = {
    401: problem_openapi("Bearer token missing or invalid"),
    422: problem_openapi("Request does not match the endpoint contract"),
    501: problem_openapi("Agent Zero contract stub"),
}


class PrepareRequest(ContractRequest):
    thread_id: UUID
    agent_id: str
    machine_id: str
    principal_id: str
    project_key: str | None = None
    agent_kind: str | None = None
    prompt: str
    model_context_tokens: int


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
    status_code=501,
    response_class=ProblemJSONResponse,
    responses=STUB_RESPONSES,
)
async def prepare(_: PrepareRequest, request: Request) -> ProblemJSONResponse:
    return not_implemented("POST /v1/inject/prepare", request.url.path)


@router.post(
    "/v1/inject/commit",
    status_code=501,
    response_class=ProblemJSONResponse,
    responses=STUB_RESPONSES,
)
async def commit(_: CommitRequest, request: Request) -> ProblemJSONResponse:
    return not_implemented("POST /v1/inject/commit", request.url.path)


@router.post(
    "/v1/feedback",
    status_code=501,
    response_class=ProblemJSONResponse,
    responses=STUB_RESPONSES,
)
async def feedback(_: FeedbackRequest, request: Request) -> ProblemJSONResponse:
    return not_implemented("POST /v1/feedback", request.url.path)
