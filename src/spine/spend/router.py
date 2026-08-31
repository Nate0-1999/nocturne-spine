"""Authenticated HTTP boundary for receipt ingestion and M3SP's table read."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from spine.problems import ProblemJSONResponse, problem_openapi, problem_response
from spine.spend.contracts import (
    SpendEventsRequest,
    SpendEventsResponse,
    SpendTableSnapshot,
)
from spine.spend.service import SpendEventConflictError, SpendService

router = APIRouter(prefix="/v1/spend", tags=["spend"])


@router.get(
    "/table",
    response_model=SpendTableSnapshot,
    responses={
        401: problem_openapi("Bearer token missing or invalid"),
        422: problem_openapi("Request does not match the endpoint contract"),
        500: problem_openapi("Unexpected service failure"),
    },
)
async def read_spend_table(
    request: Request,
    thread_id: Annotated[list[UUID] | None, Query()] = None,
    scope: Literal["global", "threads"] = "global",
) -> SpendTableSnapshot:
    """Return the global ledger projection or one explicit thread/stack slice."""

    scoped_threads = thread_id if thread_id is not None else ([] if scope == "threads" else None)
    return await _service(request).table(scoped_threads)


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
