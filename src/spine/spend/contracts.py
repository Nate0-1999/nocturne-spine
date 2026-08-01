"""Exact M2A wire contracts for ADR-024 receipt lines."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictStr,
    field_validator,
    model_validator,
)

_ULID_PATTERN = re.compile(r"^[0-7][0-9A-HJKMNP-TV-Z]{25}$", re.IGNORECASE)


def _ulid(value: str) -> str:
    if not _ULID_PATTERN.fullmatch(value):
        raise ValueError("value must be a ULID")
    return value.upper()


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("value must not be blank")
    if value != value.strip():
        raise ValueError("value must not contain surrounding whitespace")
    return value


type ULID = Annotated[StrictStr, AfterValidator(_ulid)]
type NonBlankString = Annotated[StrictStr, AfterValidator(_nonblank)]
type SpendProductType = Literal["llm.request", "llm.embedding"]
type SpendBasis = Literal["measured", "allocated", "estimated"]
type SpendBehavior = Literal["variable", "fixed", "step"]
type SpendPurpose = Literal[
    "building",
    "extraction",
    "curation",
    "judge",
    "remember",
    "embedding",
    "scout",
]


class SpendContract(BaseModel):
    """Closed, finite JSON object used at the spend boundary."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class SpendEventInput(SpendContract):
    """One row-reads-as-a-sentence ADR-024 receipt line."""

    event_uid: ULID
    ts: datetime
    product_type: SpendProductType
    quantity_type: NonBlankString
    unit_of_measure: NonBlankString
    quantity: Decimal = Field(gt=0, max_digits=30, decimal_places=9)
    cost_usd: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=12)
    basis: SpendBasis
    behavior: SpendBehavior
    purpose: SpendPurpose
    principal_id: NonBlankString | None = None
    machine_id: NonBlankString | None = None
    origin_agent: NonBlankString | None = None
    thread_id: UUID | None = None
    run_id: ULID | None = None
    prompt_id: ULID | None = None
    memory_id: UUID | None = None
    model: NonBlankString | None = None
    provider: NonBlankString | None = None
    quantization: NonBlankString | None = None
    ref: NonBlankString
    meta: dict[str, JsonValue] = Field(default_factory=dict)

    @field_validator("ts")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ts must include a UTC offset")
        return value


class SpendEventsRequest(SpendContract):
    """One atomic receipt batch for a provider response."""

    events: list[SpendEventInput] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def require_unique_event_ids(self) -> SpendEventsRequest:
        event_ids = [event.event_uid for event in self.events]
        if len(set(event_ids)) != len(event_ids):
            raise ValueError("events must have unique event_uid values")
        return self


class SpendEventsResponse(SpendContract):
    """Idempotent acceptance count, including identical replays."""

    accepted: int = Field(strict=True, ge=1)


def event_values(event: SpendEventInput) -> dict[str, Any]:
    """Return database-ready values without lossy JSON number conversion."""

    return event.model_dump(mode="python")


__all__ = [
    "SpendBasis",
    "SpendBehavior",
    "SpendContract",
    "SpendEventInput",
    "SpendEventsRequest",
    "SpendEventsResponse",
    "SpendProductType",
    "SpendPurpose",
    "event_values",
]
