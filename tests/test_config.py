"""C.5 defaults and fixed storage-shape configuration tests."""

from decimal import Decimal
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import ScriptedEmbeddingProvider
from pydantic import ValidationError

import spine.main as spine_main
from spine.config import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://unused:unused@localhost/unused",
        token="test-token",
        **overrides,
    )


def test_c5_dedup_and_embedding_defaults_are_exact() -> None:
    """SPEC C.5 is defended by verifying that c5 dedup and embedding defaults are exact; this
    prevents drift in the runtime configuration boundary.
    """
    settings = _settings()

    assert settings.dedup_dup == 0.92
    assert settings.dedup_sim == 0.80
    assert settings.embed_base_url == "https://openrouter.ai/api/v1"
    assert settings.embed_model == "openai/text-embedding-3-small"
    assert settings.embed_dim == 1536
    assert settings.learner_min_dispositions == 25
    assert settings.learner_holdout_fraction == 0.20
    assert settings.learner_passive_discount == 0.25
    assert settings.learner_pair_margin == 0.05
    assert settings.learner_bias_l2 == 1.0
    assert settings.learner_win_margin == 1.0
    assert settings.learner_schedule_hours is None
    assert settings.reconciliation_hours == 24
    assert settings.reconciliation_tolerance_usd == Decimal("0.000001")


def test_runtime_environment_cannot_override_artifact_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SPEC C.5 is defended by verifying that runtime environment cannot override artifact
    version; this prevents drift in the runtime configuration boundary.
    """
    monkeypatch.setenv("SPINE_VERSION", "not-the-installed-version")

    assert "version" not in Settings.model_fields
    assert not hasattr(_settings(), "version")


def test_config_rejects_overlapping_bands_and_wrong_storage_dimension() -> None:
    """SPEC C.5 is defended by verifying that config rejects overlapping bands and wrong
    storage dimension; this prevents drift in the runtime configuration boundary.
    """
    with pytest.raises(ValidationError, match="dedup_sim must be less than dedup_dup"):
        _settings(dedup_sim=0.92, dedup_dup=0.92)

    with pytest.raises(ValidationError):
        _settings(embed_dim=512)
    with pytest.raises(ValidationError):
        _settings(learner_holdout_fraction=0.5)
    with pytest.raises(ValidationError):
        _settings(learner_passive_discount=0.0)
    with pytest.raises(ValidationError):
        _settings(learner_schedule_hours=0.0)


@pytest.mark.parametrize(
    ("environment", "expected_base_url", "expected_model"),
    [
        ({}, "https://openrouter.ai/api/v1", "openai/text-embedding-3-small"),
        (
            {
                "SPINE_EMBED_BASE_URL": "https://api.openai.com/v1",
                "SPINE_EMBED_MODEL": "text-embedding-3-small",
            },
            "https://api.openai.com/v1",
            "text-embedding-3-small",
        ),
    ],
)
def test_embedding_runtime_wires_default_and_direct_provider_without_network(
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str],
    expected_base_url: str,
    expected_model: str,
) -> None:
    """SPEC C.5 is defended by verifying that embedding runtime wires default and direct
    provider without network; this prevents drift in the runtime configuration boundary.
    """
    monkeypatch.delenv("SPINE_EMBED_BASE_URL", raising=False)
    monkeypatch.delenv("SPINE_EMBED_MODEL", raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)

    provider = ScriptedEmbeddingProvider()
    provider.aclose = AsyncMock()  # type: ignore[attr-defined]
    fake_adapter = Mock(return_value=provider)

    def unused_session_factory() -> None:
        raise AssertionError("configuration test must not access Postgres")

    monkeypatch.setattr(spine_main, "OpenAIEmbeddingProvider", fake_adapter)
    app = spine_main.create_app(
        _settings(openai_api_key="compatible-key"),
        session_factory=unused_session_factory,  # type: ignore[arg-type]
    )

    fake_adapter.assert_called_once()
    assert fake_adapter.call_args.kwargs == {
        "api_key": "compatible-key",
        "model": expected_model,
        "dimensions": 1536,
        "base_url": expected_base_url,
        "receipt_sink": app.state.spend_service,
    }
    assert (app.state.reconciliation_service is not None) is (
        expected_base_url == "https://openrouter.ai/api/v1"
    )
