"""Closed HTTP contracts for M2H extraction consent."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from spine.contracts import ContractModel, MemoryKind, MemoryUnit, SimilarityMemoryCard

Verdict = Literal["new", "merge", "supersede", "contradict"]


class ExtractionCandidate(ContractModel):
    label: str = Field(min_length=1)
    body: str = Field(min_length=1)
    kind: MemoryKind
    keywords: list[str] = Field(min_length=2, max_length=5)
    project_key: str | None = None
    verdict: Verdict
    target_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_candidate_shape(self) -> "ExtractionCandidate":
        if any(not value.strip() or value != value.strip() for value in self.keywords):
            raise ValueError("candidate keywords must be trimmed and nonblank")
        if len(set(self.keywords)) != len(self.keywords):
            raise ValueError("candidate keywords must be unique")
        if len(set(self.target_ids)) != len(self.target_ids):
            raise ValueError("candidate target_ids must be unique")
        if self.verdict == "new" and self.target_ids:
            raise ValueError("a new verdict cannot implicate target memories")
        if self.verdict != "new" and not self.target_ids:
            raise ValueError("a non-new verdict requires at least one target memory")
        return self


class ExtractionRequest(ContractModel):
    principal_id: str = Field(min_length=1)
    thread_id: UUID
    machine_id: str = Field(min_length=1)
    editor: str = Field(min_length=1)
    candidates: list[ExtractionCandidate] = Field(max_length=5)


class QueueCard(ContractModel):
    item_uid: str
    candidate: MemoryUnit
    birthplace_thread_id: UUID
    verdict: Verdict
    neighbors: list[SimilarityMemoryCard]
    target_ids: list[UUID]
    state: Literal["pending", "approved", "rejected"]
    created_at: datetime


class ExtractionResponse(ContractModel):
    cards: list[QueueCard]
    duplicate_count: int = Field(ge=0)


class QueueResponse(ContractModel):
    cards: list[QueueCard]


class QueueDecisionRequest(ContractModel):
    decision: Literal["approve", "deny"]
    approval_mode: Literal["explicit", "passive"]
    actor_class: Literal["human", "passive"]
    machine_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_signal_pair(self) -> "QueueDecisionRequest":
        if self.decision == "deny" and (
            self.approval_mode != "explicit" or self.actor_class != "human"
        ):
            raise ValueError("denial must be explicit and human")
        if self.approval_mode == "passive" and self.actor_class != "passive":
            raise ValueError("passive approval requires passive actor class")
        if self.approval_mode == "explicit" and self.actor_class != "human":
            raise ValueError("explicit approval requires human actor class")
        return self


class QueueDecisionResponse(ContractModel):
    card: QueueCard
    decision: Literal["approve", "deny"]
    approval_mode: Literal["explicit", "passive"]
    actor_class: Literal["human", "passive"]
    decision_uid: str
