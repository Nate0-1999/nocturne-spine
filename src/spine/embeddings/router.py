"""Embedding-router seam with explicit broker and direct-provider adapters."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal
from urllib.parse import urlparse

import httpx

from spine.config import Settings
from spine.embeddings import (
    EmbeddingReceiptContext,
    OpenAIEmbeddingProvider,
    SpendReceiptSink,
)


class OpenRouterEmbeddingAdapter(OpenAIEmbeddingProvider):
    """OpenRouter adapter #1 over its OpenAI-compatible embeddings wire."""


class DirectEmbeddingAdapter(OpenAIEmbeddingProvider):
    """Policy-off adapter for one provider URL, model, and direct key."""


class EmbeddingRouter:
    """Stable Spine embedding interface whose implementation is one adapter."""

    def __init__(
        self,
        adapter: OpenRouterEmbeddingAdapter | DirectEmbeddingAdapter,
        *,
        mode: Literal["openrouter", "direct"],
    ) -> None:
        self._adapter = adapter
        self.mode = mode

    @property
    def model(self) -> str:
        return self._adapter.model

    @property
    def dimensions(self) -> int:
        return self._adapter.dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._adapter.embed(texts)

    async def embed_with_receipt(
        self,
        texts: Sequence[str],
        context: EmbeddingReceiptContext,
    ) -> list[list[float]]:
        return await self._adapter.embed_with_receipt(texts, context)

    async def aclose(self) -> None:
        await self._adapter.aclose()


def build_embedding_router(
    settings: Settings,
    receipt_sink: SpendReceiptSink,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> EmbeddingRouter:
    """Select brokered or direct mode from the configured provider URL."""

    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
    common = {
        "api_key": api_key,
        "model": settings.embed_model,
        "dimensions": settings.embed_dim,
        "base_url": settings.embed_base_url,
        "client": http_client,
        "receipt_sink": receipt_sink,
    }
    if urlparse(settings.embed_base_url).hostname == "openrouter.ai":
        return EmbeddingRouter(OpenRouterEmbeddingAdapter(**common), mode="openrouter")
    return EmbeddingRouter(DirectEmbeddingAdapter(**common), mode="direct")


__all__ = [
    "DirectEmbeddingAdapter",
    "EmbeddingRouter",
    "OpenRouterEmbeddingAdapter",
    "build_embedding_router",
]
