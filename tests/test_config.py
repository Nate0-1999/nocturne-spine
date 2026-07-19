"""C.5 defaults and fixed storage-shape configuration tests."""

import pytest
from pydantic import ValidationError

from spine.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://unused:unused@localhost/unused",
        token="test-token",
        **overrides,
    )


def test_c5_dedup_and_embedding_defaults_are_exact() -> None:
    settings = _settings()

    assert settings.dedup_dup == 0.92
    assert settings.dedup_sim == 0.80
    assert settings.embed_model == "text-embedding-3-small"
    assert settings.embed_dim == 1536


def test_config_rejects_overlapping_bands_and_wrong_storage_dimension() -> None:
    with pytest.raises(ValidationError, match="dedup_sim must be less than dedup_dup"):
        _settings(dedup_sim=0.92, dedup_dup=0.92)

    with pytest.raises(ValidationError):
        _settings(embed_dim=512)
