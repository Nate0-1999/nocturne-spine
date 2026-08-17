from collections.abc import Sequence

import httpx
import pytest

from spine.config import Settings
from spine.embeddings.router import build_embedding_router
from spine.spend.contracts import SpendEventInput


class ReceiptSink:
    def __init__(self) -> None:
        self.events: list[SpendEventInput] = []

    async def append(self, events: Sequence[SpendEventInput]) -> int:
        self.events.extend(events)
        return len(events)


def settings(**overrides: object) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://unused:unused@localhost/unused",
        token="test-token",
        openai_api_key="one-key",
        **overrides,
    )


def test_openrouter_is_embedding_adapter_one_without_changing_defaults() -> None:
    """SPEC C.5 and P4 are defended by routing the standing broker defaults through adapter one."""

    router = build_embedding_router(settings(), ReceiptSink())

    assert router.mode == "openrouter"
    assert router.model == "openai/text-embedding-3-small"
    assert router.dimensions == 1536


def test_direct_mode_needs_only_its_provider_url_model_and_key() -> None:
    """Invariant 13 and P4 are defended by keeping direct embeddings independent of OpenRouter."""

    router = build_embedding_router(
        settings(
            embed_base_url="https://api.openai.com/v1",
            embed_model="text-embedding-3-small",
        ),
        ReceiptSink(),
    )

    assert router.mode == "direct"
    assert router.model == "text-embedding-3-small"
    assert router.dimensions == 1536


@pytest.mark.asyncio
async def test_direct_adapter_runs_the_real_request_contract_end_to_end() -> None:
    """ADR-024 is defended by exercising the direct adapter request and vector response path."""

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [1.0, *([0.0] * 1535)]}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = build_embedding_router(
            settings(
                embed_base_url="https://api.openai.com/v1",
                embed_model="text-embedding-3-small",
                embed_dim=1536,
            ),
            ReceiptSink(),
            http_client=client,
        )
        vectors = await router.embed(["direct"])

    assert len(vectors) == 1
    assert vectors[0][:3] == [1.0, 0.0, 0.0]
    assert len(vectors[0]) == 1536
    assert requests[0].url == "https://api.openai.com/v1/embeddings"
    assert requests[0].headers["authorization"] == "Bearer one-key"
