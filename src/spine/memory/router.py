"""P0 stubs for the memory endpoints in SPEC C.4."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request

from spine.contracts import ContractRequest
from spine.problems import ProblemJSONResponse, not_implemented, problem_openapi

router = APIRouter(tags=["memory"])

MemoryKind = Literal["fact", "preference", "procedure", "project_note", "persona", "pinned"]
MemoryStatus = Literal["active", "quarantined", "tombstoned"]

STUB_RESPONSES = {
    401: problem_openapi("Bearer token missing or invalid"),
    422: problem_openapi("Request does not match the endpoint contract"),
    501: problem_openapi("Agent Zero contract stub"),
}


class CreateMemoryRequest(ContractRequest):
    principal_id: str
    label: str
    body: str
    kind: MemoryKind
    keywords: list[str] | None = None
    project_key: str | None = None
    thread_origin: str | None = None
    editor: str


class PatchMemoryRequest(ContractRequest):
    expected_revision: int
    body: str | None = None
    label: str | None = None
    keywords: list[str] | None = None
    kind: MemoryKind | None = None
    pin: bool | None = None
    status: MemoryStatus | None = None
    editor: str
    reason: str


class SearchRequest(ContractRequest):
    principal_id: str
    query: str
    k: int = 10
    project_key: str | None = None


@router.post(
    "/v1/memories",
    status_code=501,
    response_class=ProblemJSONResponse,
    responses=STUB_RESPONSES,
)
async def create_memory(_: CreateMemoryRequest, request: Request) -> ProblemJSONResponse:
    return not_implemented("POST /v1/memories", request.url.path)


@router.patch(
    "/v1/memories/{id}",
    status_code=501,
    response_class=ProblemJSONResponse,
    responses=STUB_RESPONSES,
)
async def patch_memory(
    id: UUID,
    _: PatchMemoryRequest,
    request: Request,
) -> ProblemJSONResponse:
    del id
    return not_implemented("PATCH /v1/memories/{id}", request.url.path)


@router.get(
    "/v1/memories",
    status_code=501,
    response_class=ProblemJSONResponse,
    responses=STUB_RESPONSES,
)
async def list_memories(
    request: Request,
    project_key: str | None = None,
    status: MemoryStatus | None = None,
    q: str | None = None,
) -> ProblemJSONResponse:
    del project_key, status, q
    return not_implemented("GET /v1/memories", request.url.path)


@router.post(
    "/v1/search",
    status_code=501,
    response_class=ProblemJSONResponse,
    responses=STUB_RESPONSES,
)
async def search(_: SearchRequest, request: Request) -> ProblemJSONResponse:
    return not_implemented("POST /v1/search", request.url.path)
