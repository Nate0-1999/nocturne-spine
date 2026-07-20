"""RFC 7807 response helpers used by the P0 HTTP boundary."""

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class ProblemDetail(BaseModel):
    """RFC 7807 problem details with an optional endpoint extension."""

    model_config = ConfigDict(extra="allow")

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str
    endpoint: str | None = None


class ProblemJSONResponse(JSONResponse):
    """JSON response with RFC 7807's registered media type."""

    media_type = "application/problem+json"


def problem_openapi(description: str) -> dict[str, Any]:
    """Return an inline OpenAPI response entry for RFC 7807 errors."""

    return {
        "description": description,
        "content": {
            "application/problem+json": {
                "schema": ProblemDetail.model_json_schema(),
            }
        },
    }


def problem_response(
    *,
    status: int,
    title: str,
    detail: str,
    instance: str,
    endpoint: str | None = None,
    headers: dict[str, str] | None = None,
    extensions: dict[str, Any] | None = None,
) -> ProblemJSONResponse:
    """Build an `application/problem+json` response."""

    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": instance,
    }
    if endpoint is not None:
        body["endpoint"] = endpoint
    if extensions:
        body.update(extensions)
    return ProblemJSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
        headers=headers,
    )
