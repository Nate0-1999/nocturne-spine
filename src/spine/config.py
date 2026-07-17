"""Spine configuration and the authoritative M1 defaults from SPEC C.5."""

from pydantic import Field, SecretStr
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
    embed_model: str = "text-embedding-3-small"
    embed_dim: int = Field(default=1536, gt=0)
    memory_max_tokens: int = Field(default=128, gt=0)
    label_max: int = Field(default=64, gt=0)
    chat_model: str = "anthropic:claude-sonnet-4-6"
