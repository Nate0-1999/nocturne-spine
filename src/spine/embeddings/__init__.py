"""Provider-pluggable embedding boundary and the production OpenAI adapter."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    """The embedding capability consumed by the Spine memory service."""

    model: str
    dimensions: int

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed ``texts`` while preserving their input order."""


class EmbeddingProviderError(RuntimeError):
    """Base class for expected embedding-provider failures."""


class EmbeddingConfigurationError(EmbeddingProviderError):
    """The provider cannot run because its configuration is invalid."""


class EmbeddingInputError(EmbeddingProviderError):
    """The caller supplied a value outside the embedding boundary contract."""


class EmbeddingTransportError(EmbeddingProviderError):
    """The provider request did not receive an HTTP response."""


class EmbeddingAPIError(EmbeddingProviderError):
    """The provider returned a non-success HTTP response."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"OpenAI embeddings request failed with HTTP {status_code}: {detail}")


class EmbeddingResponseError(EmbeddingProviderError):
    """A successful provider response did not satisfy the vector contract."""


async def embed_one(
    provider: EmbeddingProvider,
    text: str,
    *,
    expected_dimensions: int | None = None,
) -> list[float]:
    """Embed one text and validate any injected provider's vector response."""

    vectors = await provider.embed([text])
    if len(vectors) != 1:
        raise EmbeddingResponseError(
            f"embedding provider returned {len(vectors)} vectors for one input"
        )
    vector = vectors[0]
    dimensions = provider.dimensions if expected_dimensions is None else expected_dimensions
    if len(vector) != dimensions:
        raise EmbeddingResponseError(
            f"embedding provider returned dimension {len(vector)}; expected {dimensions}"
        )
    normalized: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EmbeddingResponseError("embedding provider returned a non-numeric value")
        number = float(value)
        if not math.isfinite(number):
            raise EmbeddingResponseError("embedding provider returned a non-finite value")
        normalized.append(number)
    if math.fsum(value * value for value in normalized) == 0.0:
        raise EmbeddingResponseError("embedding provider returned a zero-norm vector")
    return normalized


class OpenAIEmbeddingProvider:
    """Embed text with OpenAI's ``POST /v1/embeddings`` endpoint."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not model.strip():
            raise EmbeddingConfigurationError("embedding model must not be blank")
        if isinstance(dimensions, bool) or not isinstance(dimensions, int) or dimensions <= 0:
            raise EmbeddingConfigurationError("embedding dimensions must be a positive integer")
        if not base_url.strip():
            raise EmbeddingConfigurationError("OpenAI base URL must not be blank")

        self.model = model
        self.dimensions = dimensions
        self._api_key = api_key
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._timeout = timeout
        self._client = client or httpx.AsyncClient()
        self._owns_client = client is None

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return validated vectors in the same order as ``texts``."""

        api_key = self._required_api_key()
        inputs = self._validate_inputs(texts)
        if not inputs:
            return []

        try:
            response = await self._client.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "input": inputs,
                    "model": self.model,
                    "dimensions": self.dimensions,
                    "encoding_format": "float",
                },
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            raise EmbeddingTransportError("OpenAI embeddings request failed") from exc

        if not response.is_success:
            raise EmbeddingAPIError(response.status_code, _api_error_detail(response))

        try:
            payload: object = response.json()
        except ValueError as exc:
            raise EmbeddingResponseError("OpenAI embeddings response was not valid JSON") from exc
        return _validated_vectors(payload, expected_count=len(inputs), dimensions=self.dimensions)

    async def aclose(self) -> None:
        """Close the internally created HTTP client, if this provider owns it."""

        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> OpenAIEmbeddingProvider:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    def _required_api_key(self) -> str:
        if self._api_key is None or not self._api_key.strip():
            raise EmbeddingConfigurationError(
                "OpenAI API key is required before embeddings can be requested"
            )
        return self._api_key.strip()

    @staticmethod
    def _validate_inputs(texts: Sequence[str]) -> list[str]:
        if isinstance(texts, str):
            raise EmbeddingInputError("embedding input must be a sequence of strings, not a string")
        inputs = list(texts)
        if any(not isinstance(text, str) for text in inputs):
            raise EmbeddingInputError("every embedding input must be a string")
        return inputs


def _api_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "provider rejected the request"

    if isinstance(payload, Mapping):
        error = payload.get("error")
        if isinstance(error, Mapping):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
    return "provider rejected the request"


def _validated_vectors(
    payload: object,
    *,
    expected_count: int,
    dimensions: int,
) -> list[list[float]]:
    if not isinstance(payload, Mapping):
        raise EmbeddingResponseError("OpenAI embeddings response must be a JSON object")
    data = payload.get("data")
    if not isinstance(data, list):
        raise EmbeddingResponseError("OpenAI embeddings response must contain a data list")
    if len(data) != expected_count:
        raise EmbeddingResponseError(
            f"OpenAI embeddings response returned {len(data)} vectors for {expected_count} inputs"
        )

    vectors_by_index: dict[int, list[float]] = {}
    for item in data:
        if not isinstance(item, Mapping):
            raise EmbeddingResponseError("OpenAI embeddings data items must be JSON objects")
        index = item.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise EmbeddingResponseError("OpenAI embeddings data index must be an integer")
        if index < 0 or index >= expected_count:
            raise EmbeddingResponseError(f"OpenAI embeddings data index {index} is out of range")
        if index in vectors_by_index:
            raise EmbeddingResponseError(f"OpenAI embeddings data index {index} is duplicated")

        embedding = item.get("embedding")
        if not isinstance(embedding, list):
            raise EmbeddingResponseError(f"OpenAI embedding at index {index} must be a JSON array")
        if len(embedding) != dimensions:
            raise EmbeddingResponseError(
                f"OpenAI embedding at index {index} has dimension {len(embedding)}; "
                f"expected {dimensions}"
            )

        vector: list[float] = []
        for value in embedding:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise EmbeddingResponseError(
                    f"OpenAI embedding at index {index} contains a non-numeric value"
                )
            normalized = float(value)
            if not math.isfinite(normalized):
                raise EmbeddingResponseError(
                    f"OpenAI embedding at index {index} contains a non-finite value"
                )
            vector.append(normalized)
        if math.fsum(value * value for value in vector) == 0.0:
            raise EmbeddingResponseError(f"OpenAI embedding at index {index} has zero norm")
        vectors_by_index[index] = vector

    missing = set(range(expected_count)).difference(vectors_by_index)
    if missing:
        missing_text = ", ".join(str(index) for index in sorted(missing))
        raise EmbeddingResponseError(
            f"OpenAI embeddings response is missing indices: {missing_text}"
        )
    return [vectors_by_index[index] for index in range(expected_count)]


__all__ = [
    "EmbeddingAPIError",
    "EmbeddingConfigurationError",
    "EmbeddingInputError",
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingResponseError",
    "EmbeddingTransportError",
    "OpenAIEmbeddingProvider",
    "embed_one",
]
