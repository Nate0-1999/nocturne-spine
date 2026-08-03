"""Exact A-035 wire contracts for the Memory Graph and Injection Console."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)

from spine.contracts import MemoryFeatures, MemoryUnit


def _nonblank(value: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError("value must be nonblank without surrounding whitespace")
    return value


type NonBlankString = Annotated[StrictStr, AfterValidator(_nonblank)]
type SignedDecimalString = Annotated[
    StrictStr,
    Field(pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$"),
]
type NonNegativeInt = Annotated[StrictInt, Field(ge=0)]
type PositiveInt = Annotated[StrictInt, Field(gt=0)]
type FeatureName = Literal["sem", "kw", "time", "proj", "freq", "hist"]


class M2KContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MemoryGraphQuery(M2KContract):
    principal_id: NonBlankString
    memory_ids: list[UUID] | None

    @model_validator(mode="after")
    def unique_memory_ids(self) -> MemoryGraphQuery:
        if self.memory_ids is not None and len(self.memory_ids) != len(set(self.memory_ids)):
            raise ValueError("memory_ids must be unique")
        return self


class RevisionTrailItem(M2KContract):
    rev_uid: NonBlankString
    parent_uid: NonBlankString | None
    revision: PositiveInt | None
    ts: AwareDatetime
    reason: str


class MemoryGraphNode(M2KContract):
    memory: MemoryUnit
    in_current_context: bool
    revisions: list[RevisionTrailItem]


class MemoryGraphEdge(M2KContract):
    kind: Literal["similarity", "lineage", "edit_trail"]
    from_memory_id: UUID
    to_memory_id: UUID
    similarity: SignedDecimalString | None = None
    edge_type: Literal["merged_from", "supersedes", "contradicts", "relates_to"] | None = None
    revision_count: PositiveInt | None = None

    @model_validator(mode="after")
    def exact_payload_for_kind(self) -> MemoryGraphEdge:
        populated = (
            self.similarity is not None,
            self.edge_type is not None,
            self.revision_count is not None,
        )
        expected = {
            "similarity": (True, False, False),
            "lineage": (False, True, False),
            "edit_trail": (False, False, True),
        }[self.kind]
        if populated != expected:
            raise ValueError("graph edge payload does not match its kind")
        return self


class MemoryGraphSnapshot(M2KContract):
    as_of: AwareDatetime
    graph_edge_sim: float
    nodes: list[MemoryGraphNode]
    edges: list[MemoryGraphEdge]
    omitted_memory_ids: list[UUID]


class ScorerConsoleQuery(M2KContract):
    principal_id: NonBlankString
    thread_id: UUID | None
    as_of: AwareDatetime | Literal["now"] = "now"


class ParameterRange(M2KContract):
    minimum: float
    maximum: float | None
    step: float
    exclusive_minimum: bool = False


class ScorerDescriptor(M2KContract):
    id: NonBlankString
    label: NonBlankString
    type: Literal["number", "integer"]
    range: ParameterRange
    default: float | int
    scope: Literal["global"] = "global"
    authority: Literal["law-bound"] = "law-bound"


class ScorerValues(M2KContract):
    tau: Annotated[StrictFloat, Field(ge=0.0, le=1.0)]
    top_k: Annotated[StrictInt, Field(ge=1, le=8)]
    budget_tokens: PositiveInt
    half_life_time_days: Annotated[StrictFloat, Field(gt=0.0)]
    half_life_hist_days: Annotated[StrictFloat, Field(gt=0.0)]
    weights: dict[FeatureName, Annotated[StrictFloat, Field(ge=0.0, le=1.0)]]

    @model_validator(mode="after")
    def exact_weight_vector(self) -> ScorerValues:
        required = {"sem", "kw", "time", "proj", "freq", "hist"}
        if set(self.weights) != required:
            raise ValueError("weights must contain the exact six scorer features")
        if abs(sum(self.weights.values()) - 1.0) > 1e-9:
            raise ValueError("weights must sum to one")
        return self


class ScorerConfigurationView(M2KContract):
    version: NonBlankString
    created_at: AwareDatetime
    status: Literal["active", "proposed", "inactive"]
    values: ScorerValues
    replay: dict[str, Any] | None


class ScorerActivationView(M2KContract):
    event_uid: NonBlankString
    version: NonBlankString
    previous_version: NonBlankString
    actor_class: Literal["human", "passive"]
    machine_id: NonBlankString
    reason: Literal["human_control", "learner_proposal"]
    changes: dict[str, Any]
    ts: AwareDatetime


class AccuracyPoint(M2KContract):
    version: NonBlankString
    created_at: AwareDatetime
    status: Literal["measured", "not_recorded"]
    accuracy_percent: SignedDecimalString | None
    holdout_dispositions: NonNegativeInt | None
    disagreements: NonNegativeInt | None


class ContributionBreakdown(M2KContract):
    sem: SignedDecimalString
    kw: SignedDecimalString
    time: SignedDecimalString
    proj: SignedDecimalString
    freq: SignedDecimalString
    hist: SignedDecimalString
    bias: SignedDecimalString


class CandidateScorePoint(M2KContract):
    event_uid: NonBlankString
    ts: AwareDatetime
    scorer_version: NonBlankString
    score: SignedDecimalString
    rank: PositiveInt
    shown_as: Literal["injected", "near_miss", "pinned"]
    outcome: str | None
    features: MemoryFeatures
    contributions: ContributionBreakdown


class CandidateScoreHistory(M2KContract):
    memory_id: UUID
    label: str
    kind: str
    points: list[CandidateScorePoint]


class ScorerConsoleSnapshot(M2KContract):
    as_of: AwareDatetime
    scope: Literal["GLOBAL", "CURRENT"]
    thread_id: UUID | None
    descriptors: list[ScorerDescriptor]
    active_version: NonBlankString
    configurations: list[ScorerConfigurationView]
    activations: list[ScorerActivationView]
    proposed_versions: list[ScorerConfigurationView]
    accuracy: list[AccuracyPoint]
    candidates: list[CandidateScoreHistory]


class CreateScorerConfigRequest(M2KContract):
    event_uid: NonBlankString
    base_version: NonBlankString
    values: ScorerValues
    actor_class: Literal["human"]
    machine_id: NonBlankString


class ActivateScorerConfigRequest(M2KContract):
    event_uid: NonBlankString
    actor_class: Literal["human"]
    machine_id: NonBlankString


__all__ = [
    "ActivateScorerConfigRequest",
    "CandidateScoreHistory",
    "CandidateScorePoint",
    "ContributionBreakdown",
    "CreateScorerConfigRequest",
    "MemoryGraphQuery",
    "MemoryGraphSnapshot",
    "ScorerConfigurationView",
    "ScorerConsoleQuery",
    "ScorerConsoleSnapshot",
    "ScorerDescriptor",
    "ScorerValues",
]
