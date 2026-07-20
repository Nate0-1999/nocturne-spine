"""Shared strict models for the exact SPEC C.4 wire contract."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, RootModel

MemoryKind = Literal["fact", "preference", "procedure", "project_note", "persona", "pinned"]
MemoryStatus = Literal["active", "quarantined", "tombstoned"]


class ContractModel(BaseModel):
    """Reject fields outside the literal cross-repository contract."""

    model_config = ConfigDict(extra="forbid")


class ContractRequest(ContractModel):
    """Marker base for exact C.4 request bodies."""


class MemoryFeatures(ContractModel):
    sem: float
    kw: float
    time: float
    proj: float
    freq: float
    hist: float


class MemoryCard(ContractModel):
    memory_id: UUID
    label: str
    body: str
    kind: MemoryKind
    pin: bool
    score: float
    features: MemoryFeatures | None
    rank: int | None


class ScoredMemoryCard(MemoryCard):
    """Inject/prepare card, where C.4 requires scoring details."""

    features: MemoryFeatures
    rank: int


class SimilarityMemoryCard(MemoryCard):
    """Dedup/search card, where C.4 requires scoring details to be null."""

    features: None
    rank: None


class MemoryUnit(ContractModel):
    memory_id: UUID
    principal_id: str
    label: str
    body: str
    kind: MemoryKind
    keywords: list[str]
    project_key: str | None
    thread_origin: str | None
    origin_path: str | None
    pin: bool
    status: MemoryStatus
    revision: int
    stats: dict[str, Any]
    bias: float
    embedding_model: str
    created_at: datetime
    updated_at: datetime


class PrepareResponse(ContractModel):
    injection_id: UUID
    snapshot_ts: datetime
    scorer_version: str
    injected: list[ScoredMemoryCard]
    near_misses: list[ScoredMemoryCard]


class CommitResponse(ContractModel):
    final_block: str
    wrong_removed: list[MemoryUnit]


class FeedbackResponse(ContractModel):
    ok: Literal[True]


class CreatedMemoryResponse(ContractModel):
    created: MemoryUnit


class SimilarMemoryResponse(ContractModel):
    created: None
    similar: list[SimilarityMemoryCard]


class LabelConflictDetail(ContractModel):
    memory_id: UUID
    label: str


class LabelConflictResponse(ContractModel):
    label_conflict: LabelConflictDetail


class DuplicateMemoryResponse(ContractModel):
    duplicate_of: SimilarityMemoryCard


class CreateMemoryConflictResponse(RootModel[LabelConflictResponse | DuplicateMemoryResponse]):
    """The two exact 409 bodies for memory creation."""


class RevisionConflictResponse(ContractModel):
    conflict: MemoryUnit


class PatchMemoryConflictResponse(RootModel[LabelConflictResponse | RevisionConflictResponse]):
    """The two exact 409 bodies for a memory patch."""


class MemoryListResponse(ContractModel):
    items: list[MemoryUnit]
    total: int
    limit: int
    offset: int


class SearchResponse(ContractModel):
    results: list[SimilarityMemoryCard]
