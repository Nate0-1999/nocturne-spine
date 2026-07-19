"""Production embedding adapter contract tests using an in-process HTTP transport."""

from __future__ import annotations

import json
import math
from collections.abc import Callable

import httpx
import pytest

from spine.embeddings import (
    EmbeddingAPIError,
    EmbeddingConfigurationError,
    EmbeddingInputError,
    EmbeddingResponseError,
    EmbeddingTransportError,
    OpenAIEmbeddingProvider,
)


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_openai_request_and_response_order_follow_the_provider_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://openai.example/v1/embeddings"
        assert request.headers["authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "input": ["first", "second"],
            "model": "text-embedding-test",
            "dimensions": 3,
            "encoding_format": "float",
        }
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [4, 5.0, 6]},
                    {"index": 0, "embedding": [1.0, 2, 3.0]},
                ]
            },
        )

    async with _client(handler) as client:
        provider = OpenAIEmbeddingProvider(
            api_key=" test-key ",
            model="text-embedding-test",
            dimensions=3,
            base_url="https://openai.example/v1/",
            client=client,
        )
        vectors = await provider.embed(["first", "second"])

    assert provider.model == "text-embedding-test"
    assert provider.dimensions == 3
    assert vectors == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]


async def test_missing_api_key_fails_at_call_time_without_an_http_request() -> None:
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"data": []})

    async with _client(handler) as client:
        provider = OpenAIEmbeddingProvider(api_key=None, dimensions=3, client=client)
        with pytest.raises(EmbeddingConfigurationError, match="API key is required"):
            await provider.embed(["memory"])

    assert called is False


async def test_empty_batch_is_local_but_still_requires_provider_configuration() -> None:
    called = False

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    async with _client(handler) as client:
        provider = OpenAIEmbeddingProvider(api_key="test-key", dimensions=3, client=client)
        assert await provider.embed([]) == []

    assert called is False


async def test_non_sequence_and_mixed_inputs_raise_typed_errors() -> None:
    async with _client(lambda _: httpx.Response(500)) as client:
        provider = OpenAIEmbeddingProvider(api_key="test-key", dimensions=3, client=client)
        with pytest.raises(EmbeddingInputError, match="not a string"):
            await provider.embed("memory")
        with pytest.raises(EmbeddingInputError, match="every embedding input"):
            await provider.embed(["memory", 7])  # type: ignore[list-item]


async def test_transport_and_api_failures_remain_distinct() -> None:
    def disconnected(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async with _client(disconnected) as client:
        provider = OpenAIEmbeddingProvider(api_key="test-key", dimensions=3, client=client)
        with pytest.raises(EmbeddingTransportError, match="request failed"):
            await provider.embed(["memory"])

    async with _client(
        lambda _: httpx.Response(429, json={"error": {"message": "rate limited"}})
    ) as client:
        provider = OpenAIEmbeddingProvider(api_key="test-key", dimensions=3, client=client)
        with pytest.raises(EmbeddingAPIError, match="HTTP 429: rate limited") as captured:
            await provider.embed(["memory"])

    assert captured.value.status_code == 429
    assert captured.value.detail == "rate limited"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"data": []}, "0 vectors for 1 inputs"),
        ({"data": [{"index": 0, "embedding": [1.0, 2.0]}]}, "dimension 2; expected 3"),
        (
            {"data": [{"index": 0, "embedding": [1.0, math.inf, 3.0]}]},
            "non-finite value",
        ),
        ({"data": [{"index": 0, "embedding": [0.0, 0.0, 0.0]}]}, "zero norm"),
        ({"data": [{"index": 1, "embedding": [1.0, 2.0, 3.0]}]}, "out of range"),
        (
            {"data": [{"index": 0, "embedding": [1.0, "2", 3.0]}]},
            "non-numeric value",
        ),
    ],
)
async def test_malformed_success_responses_raise_typed_errors(
    payload: object,
    message: str,
) -> None:
    response_content = json.dumps(payload).encode()
    async with _client(
        lambda _: httpx.Response(
            200,
            content=response_content,
            headers={"content-type": "application/json"},
        )
    ) as client:
        provider = OpenAIEmbeddingProvider(api_key="test-key", dimensions=3, client=client)
        with pytest.raises(EmbeddingResponseError, match=message):
            await provider.embed(["memory"])
