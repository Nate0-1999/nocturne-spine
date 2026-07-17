"""P0 stubs for the memory endpoints in SPEC C.4."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from spine.contracts import (
    ContractRequest,
    CreatedMemoryResponse,
    CreateMemoryConflictResponse,
    MemoryKind,
    MemoryListResponse,
    MemoryStatus,
    MemoryUnit,
    PatchMemoryConflictResponse,
    SearchResponse,
    SimilarMemoryResponse,
)
from spine.problems import ProblemJSONResponse, not_implemented, problem_openapi

router = APIRouter(tags=["memory"])

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
    machine_id: str
    force: bool = False


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
    machine_id: str


class SearchRequest(ContractRequest):
    principal_id: str
    query: str
    k: int = 10
    project_key: str | None = None


@router.post(
    "/v1/memories",
    status_code=201,
    response_model=CreatedMemoryResponse,
    responses=STUB_RESPONSES
    | {
        200: {
            "description": "Similar memories require an explicit force retry",
            "model": SimilarMemoryResponse,
        },
        409: {
            "description": "Active-label collision or hard duplicate",
            "model": CreateMemoryConflictResponse,
        },
    },
)
async def create_memory(_: CreateMemoryRequest, request: Request) -> ProblemJSONResponse:
    return not_implemented("POST /v1/memories", request.url.path)


@router.patch(
    "/v1/memories/{id}",
    response_model=MemoryUnit,
    responses=STUB_RESPONSES
    | {
        409: {
            "description": "CAS or active-label conflict",
            "model": PatchMemoryConflictResponse,
        }
    },
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
    response_model=MemoryListResponse,
    responses=STUB_RESPONSES,
)
async def list_memories(
    request: Request,
    project_key: str | None = None,
    status: MemoryStatus | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(le=200)] = 50,
    offset: int = 0,
) -> ProblemJSONResponse:
    del project_key, status, q, limit, offset
    return not_implemented("GET /v1/memories", request.url.path)


@router.post(
    "/v1/search",
    response_model=SearchResponse,
    responses=STUB_RESPONSES,
)
async def search(_: SearchRequest, request: Request) -> ProblemJSONResponse:
    return not_implemented("POST /v1/search", request.url.path)
