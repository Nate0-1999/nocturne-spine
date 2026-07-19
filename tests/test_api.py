"""Health, auth, validation, and remaining route-stub contract tests."""

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

STUB_CASES: list[tuple[str, str, str, dict[str, Any] | None]] = [
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
        "/v1/search",
        "POST /v1/search",
        {"principal_id": "owner", "query": "editor"},
    ),
]

C4_ROUTES = {
    ("POST", "/v1/inject/prepare"),
    ("POST", "/v1/inject/commit"),
    ("POST", "/v1/feedback"),
    ("POST", "/v1/memories"),
    ("PATCH", "/v1/memories/{id}"),
    ("GET", "/v1/memories"),
    ("POST", "/v1/search"),
}


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
async def test_unimplemented_c4_routes_are_named_rfc7807_stubs(
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


async def test_v15_machine_id_is_required_on_create_and_patch(app: FastAPI) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create = await client.post(
            "/v1/memories",
            headers=headers,
            json={
                "principal_id": "owner",
                "label": "Editor preference",
                "body": "The owner prefers tabs.",
                "kind": "preference",
                "editor": "user",
            },
        )
        patch = await client.patch(
            f"/v1/memories/{MEMORY_ID}",
            headers=headers,
            json={"expected_revision": 1, "editor": "user", "reason": "fix"},
        )

    _assert_problem(create, status=422, endpoint="POST /v1/memories")
    _assert_problem(patch, status=422, endpoint=f"PATCH /v1/memories/{MEMORY_ID}")
    assert {error["loc"][-1] for error in create.json()["errors"]} == {"machine_id"}
    assert {error["loc"][-1] for error in patch.json()["errors"]} == {"machine_id"}


async def test_v15_list_paging_contract_is_validated(app: FastAPI) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        excessive = await client.get("/v1/memories?limit=201", headers=headers)
        empty = await client.get("/v1/memories?limit=0", headers=headers)
        negative = await client.get("/v1/memories?offset=-1", headers=headers)

    _assert_problem(excessive, status=422, endpoint="GET /v1/memories")
    _assert_problem(empty, status=422, endpoint="GET /v1/memories")
    _assert_problem(negative, status=422, endpoint="GET /v1/memories")


async def test_http_errors_are_rfc7807(app: FastAPI) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/not-a-route",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    _assert_problem(response, status=404, endpoint="GET /not-a-route")


async def test_unexpected_service_errors_are_sanitized_rfc7807(app: FastAPI) -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/v1/memories",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )

    _assert_problem(response, status=500, endpoint="GET /v1/memories")
    assert response.json()["detail"] == "The request could not be completed."


def test_exactly_seven_c4_routes_are_registered(app: FastAPI) -> None:
    actual = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        if path.startswith("/v1/")
        for method in operations
    }
    assert actual == C4_ROUTES


def test_committed_openapi_is_current(app: FastAPI) -> None:
    committed = json.loads((ROOT / "openapi.json").read_text(encoding="utf-8"))
    assert committed == app.openapi()
    assert committed["components"]["securitySchemes"]["StaticBearer"] == {
        "scheme": "bearer",
        "type": "http",
    }
    assert committed["components"]["schemas"]["SearchRequest"]["additionalProperties"] is False

    create_operation = committed["paths"]["/v1/memories"]["post"]
    create_request = committed["components"]["schemas"]["CreateMemoryRequest"]
    assert {"machine_id", "editor"} <= set(create_request["required"])
    assert create_request["properties"]["force"]["default"] is False
    assert {"200", "201", "409"} <= set(create_operation["responses"])
    assert "501" not in create_operation["responses"]
    assert create_operation["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CreatedMemoryResponse"
    }
    assert create_operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/SimilarMemoryResponse"
    }
    assert create_operation["responses"]["409"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CreateMemoryConflictResponse"
    }

    patch_request = committed["components"]["schemas"]["PatchMemoryRequest"]
    assert "machine_id" in patch_request["required"]
    patch_operation = committed["paths"]["/v1/memories/{id}"]["patch"]
    assert "501" not in patch_operation["responses"]
    assert patch_operation["responses"]["409"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PatchMemoryConflictResponse"
    }
    assert "501" not in committed["paths"]["/v1/memories"]["get"]["responses"]
    prepare_operation = committed["paths"]["/v1/inject/prepare"]["post"]
    assert "501" not in prepare_operation["responses"]
    assert {"200", "409", "503"} <= set(prepare_operation["responses"])
    prepare_request = committed["components"]["schemas"]["PrepareRequest"]
    assert prepare_request["properties"]["model_context_tokens"]["exclusiveMinimum"] == 0
    commit_response = committed["paths"]["/v1/inject/commit"]["post"]
    commit_schema = commit_response["responses"]["200"]["content"]["application/json"]["schema"]
    assert commit_schema == {"$ref": "#/components/schemas/CommitResponse"}
    assert "wrong_removed" in committed["components"]["schemas"]["CommitResponse"]["required"]

    memory_unit_fields = {
        "memory_id",
        "principal_id",
        "label",
        "body",
        "kind",
        "keywords",
        "project_key",
        "thread_origin",
        "pin",
        "status",
        "revision",
        "stats",
        "bias",
        "embedding_model",
        "created_at",
        "updated_at",
    }
    assert set(committed["components"]["schemas"]["MemoryUnit"]["required"]) == memory_unit_fields
    assert set(committed["components"]["schemas"]["ScoredMemoryCard"]["required"]) == {
        "memory_id",
        "label",
        "body",
        "kind",
        "pin",
        "score",
        "features",
        "rank",
    }
    scored_properties = committed["components"]["schemas"]["ScoredMemoryCard"]["properties"]
    assert scored_properties["features"] == {"$ref": "#/components/schemas/MemoryFeatures"}
    assert scored_properties["rank"]["type"] == "integer"

    similarity_properties = committed["components"]["schemas"]["SimilarityMemoryCard"]["properties"]
    assert similarity_properties["features"]["type"] == "null"
    assert similarity_properties["rank"]["type"] == "null"
    prepare_items = committed["components"]["schemas"]["PrepareResponse"]["properties"]["injected"][
        "items"
    ]
    duplicate_card = committed["components"]["schemas"]["DuplicateMemoryResponse"]["properties"][
        "duplicate_of"
    ]
    similar_items = committed["components"]["schemas"]["SimilarMemoryResponse"]["properties"][
        "similar"
    ]["items"]
    search_items = committed["components"]["schemas"]["SearchResponse"]["properties"]["results"][
        "items"
    ]
    assert similar_items == {"$ref": "#/components/schemas/SimilarityMemoryCard"}
    assert search_items == {"$ref": "#/components/schemas/SimilarityMemoryCard"}
    assert prepare_items == {"$ref": "#/components/schemas/ScoredMemoryCard"}
    assert duplicate_card == {"$ref": "#/components/schemas/SimilarityMemoryCard"}

    list_parameters = {
        parameter["name"]: parameter
        for parameter in committed["paths"]["/v1/memories"]["get"]["parameters"]
    }
    assert list_parameters["limit"]["schema"] == {
        "default": 50,
        "maximum": 200,
        "minimum": 1,
        "title": "Limit",
        "type": "integer",
    }
    assert list_parameters["offset"]["schema"]["default"] == 0
    assert list_parameters["offset"]["schema"]["minimum"] == 0
    list_schema = committed["components"]["schemas"]["MemoryListResponse"]
    assert set(list_schema["required"]) == {"items", "total", "limit", "offset"}
