"""P0 health, auth, validation, and seven-route stub contract tests."""

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import TOKEN
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
MEMORY_ID = "00000000-0000-0000-0000-000000000001"
INJECTION_ID = "00000000-0000-0000-0000-000000000002"
THREAD_ID = "00000000-0000-0000-0000-000000000003"

STUB_CASES: list[tuple[str, str, str, dict[str, Any] | None]] = [
    (
        "POST",
        "/v1/inject/prepare",
        "POST /v1/inject/prepare",
        {
            "thread_id": THREAD_ID,
            "agent_id": "agent-1",
            "machine_id": "machine-1",
            "principal_id": "owner",
            "prompt": "hello",
            "model_context_tokens": 100_000,
        },
    ),
    (
        "POST",
        "/v1/inject/commit",
        "POST /v1/inject/commit",
        {"injection_id": INJECTION_ID, "removed": [], "added_back": []},
    ),
    (
        "POST",
        "/v1/feedback",
        "POST /v1/feedback",
        {
            "injection_id": INJECTION_ID,
            "memory_id": MEMORY_ID,
            "signal": "cited",
        },
    ),
    (
        "POST",
        "/v1/memories",
        "POST /v1/memories",
        {
            "principal_id": "owner",
            "label": "Editor preference",
            "body": "The owner prefers tabs.",
            "kind": "preference",
            "editor": "user",
        },
    ),
    (
        "PATCH",
        f"/v1/memories/{MEMORY_ID}",
        "PATCH /v1/memories/{id}",
        {"expected_revision": 1, "body": "Updated.", "editor": "user", "reason": "fix"},
    ),
    ("GET", "/v1/memories", "GET /v1/memories", None),
    (
        "POST",
        "/v1/search",
        "POST /v1/search",
        {"principal_id": "owner", "query": "editor"},
    ),
]


def _assert_problem(response: Any, *, status: int, endpoint: str) -> None:
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["title"]
    assert body["status"] == status
    assert body["detail"]
    assert body["instance"]
    assert body["endpoint"] == endpoint


async def test_healthz_and_auth_are_live(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        unauthorized = await client.get("/healthz")
        healthy = await client.get("/healthz", headers={"Authorization": f"Bearer {TOKEN}"})

    _assert_problem(unauthorized, status=401, endpoint="GET /healthz")
    assert unauthorized.headers["www-authenticate"] == "Bearer"
    assert healthy.status_code == 200
    assert healthy.json() == {"ok": True, "version": "0.1.0"}


@pytest.mark.parametrize(("method", "path", "endpoint", "body"), STUB_CASES)
async def test_c4_routes_are_named_rfc7807_stubs(
    app: FastAPI,
    method: str,
    path: str,
    endpoint: str,
    body: dict[str, Any] | None,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {TOKEN}"},
            json=body,
        )

    _assert_problem(response, status=501, endpoint=endpoint)


async def test_validation_errors_are_rfc7807(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/memories",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={},
        )

    _assert_problem(response, status=422, endpoint="POST /v1/memories")
    assert response.json()["errors"]


async def test_exact_c4_bodies_reject_extra_fields(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/search",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"principal_id": "owner", "query": "editor", "invented": True},
        )

    _assert_problem(response, status=422, endpoint="POST /v1/search")
    assert response.json()["errors"][0]["type"] == "extra_forbidden"


async def test_http_errors_are_rfc7807(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/not-a-route",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    _assert_problem(response, status=404, endpoint="GET /not-a-route")


def test_exactly_seven_c4_stubs_are_registered(app: FastAPI) -> None:
    actual = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/v1/")
        for method in operations
    }
    expected = {(method, path.replace(MEMORY_ID, "{id}")) for method, path, _, _ in STUB_CASES}
    assert actual == expected


def test_committed_openapi_is_current(app: FastAPI) -> None:
    committed = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    assert committed == app.openapi()
    assert committed["components"]["securitySchemes"]["StaticBearer"] == {
        "scheme": "bearer",
        "type": "http",
    }
    assert committed["components"]["schemas"]["SearchRequest"]["additionalProperties"] is False
