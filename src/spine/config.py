"""Spine configuration and the authoritative M1 defaults from SPEC C.5."""

from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from `SPINE_*` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="SPINE_",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    token: SecretStr
    openai_api_key: SecretStr | None = None
    version: str = "0.1.0"

    tau: float = Field(default=0.55, ge=0.0, le=1.0)
    top_k: int = Field(default=8, gt=0)
    near_miss_k: int = Field(default=3, ge=0)
    budget_tokens: int = Field(default=3000, gt=0)
    budget_pct: float = Field(default=0.05, gt=0.0, le=1.0)
    half_life_time_days: int = Field(default=14, gt=0)
    half_life_hist_days: int = Field(default=7, gt=0)
    dedup_dup: float = Field(default=0.92, ge=0.0, le=1.0)
    dedup_sim: float = Field(default=0.80, ge=0.0, le=1.0)
    never_bias_step: float = -0.15
    quarantine_kills: int = Field(default=3, gt=0)
    candidate_pool: int = Field(default=50, gt=0)
    embed_base_url: str = "https://openrouter.ai/api/v1"
    embed_model: str = "openai/text-embedding-3-small"
    embed_dim: Literal[1536] = 1536
    memory_max_tokens: int = Field(default=128, gt=0)
    label_max: int = Field(default=64, gt=0)
    chat_model: str = "anthropic:claude-sonnet-4-6"

    @model_validator(mode="after")
    def validate_dedup_bands(self) -> "Settings":
        """Keep the similar band strictly below the hard-duplicate band."""

        if self.dedup_sim >= self.dedup_dup:
            raise ValueError("dedup_sim must be less than dedup_dup")
        return self
