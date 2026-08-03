"""Exact A-028 response contract for the live Palace Vitals snapshot."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    model_validator,
)


def _nonblank(value: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError("value must be nonblank without surrounding whitespace")
    return value


type NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
type NonBlankString = Annotated[StrictStr, AfterValidator(_nonblank)]
type DecimalString = Annotated[
    StrictStr,
    Field(pattern=r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$"),
]
type GaugeStatus = Literal["measured", "not_recorded", "placeholder"]
type SpendDimension = Literal["total", "purpose", "model"]
type LifecycleMetric = Literal[
    "created",
    "reinforced",
    "superseded",
    "merged",
    "quarantined",
    "tombstoned",
    "add_backs",
]
type PalaceMetric = Literal[
    "active_units",
    "pinned_units",
    "candidates_pending",
    "edges",
    "staged_units",
    "queue_depth",
]


class VitalsContract(BaseModel):
    """Closed immutable object at the A-028 read boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SpendPoint(VitalsContract):
    minute: AwareDatetime
    cost_usd: DecimalString | None
    receipt_lines: NonNegativeInt
    unpriced_lines: NonNegativeInt

    @model_validator(mode="after")
    def require_possible_unpriced_count(self) -> SpendPoint:
        if self.unpriced_lines > self.receipt_lines:
            raise ValueError("unpriced_lines cannot exceed receipt_lines")
        return self


class SpendLane(VitalsContract):
    dimension: SpendDimension
    key: NonBlankString | None
    label: NonBlankString
    points: list[SpendPoint]

    @model_validator(mode="after")
    def require_dimension_key(self) -> SpendLane:
        if self.dimension == "total" and self.key is not None:
            raise ValueError("the total spend lane must have a null key")
        if self.dimension != "total" and self.key is None:
            raise ValueError("a dimensioned spend lane must have a key")
        return self


class SpendSnapshot(VitalsContract):
    source_view: Literal["v_spend_rate"]
    latest_minute: AwareDatetime | None
    lanes: list[SpendLane]


class LifecycleRate(VitalsContract):
    metric: LifecycleMetric
    status: GaugeStatus
    per_hour: NonNegativeInt | None
    source: NonBlankString | None

    @model_validator(mode="after")
    def require_honest_availability(self) -> LifecycleRate:
        _require_gauge_availability(
            metric=self.metric,
            status=self.status,
            value=self.per_hour,
            source=self.source,
        )
        return self


class PalaceCount(VitalsContract):
    metric: PalaceMetric
    status: GaugeStatus
    count: NonNegativeInt | None
    source: NonBlankString | None

    @model_validator(mode="after")
    def require_honest_availability(self) -> PalaceCount:
        _require_gauge_availability(
            metric=self.metric,
            status=self.status,
            value=self.count,
            source=self.source,
        )
        return self


class VitalsSnapshot(VitalsContract):
    as_of: AwareDatetime
    window_minutes: Literal[60]
    spend: SpendSnapshot
    lifecycle_rates: list[LifecycleRate]
    palace_counts: list[PalaceCount]


def _require_gauge_availability(
    *,
    metric: LifecycleMetric | PalaceMetric,
    status: GaugeStatus,
    value: int | None,
    source: str | None,
) -> None:
    if status == "measured":
        if value is None or source is None:
            raise ValueError("a measured gauge requires a value and source")
        return
    if value is not None or source is not None:
        raise ValueError("an unavailable gauge must have null value and source")


__all__ = [
    "GaugeStatus",
    "LifecycleMetric",
    "LifecycleRate",
    "PalaceCount",
    "PalaceMetric",
    "SpendDimension",
    "SpendLane",
    "SpendPoint",
    "SpendSnapshot",
    "VitalsSnapshot",
]
