"""Strict A-059 contracts for the Symphony memory bridge."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from spine.contracts import ULID, ContractModel, MemoryKind, NonBlankString
from spine.queue.contracts import QueueCard

_ORIGIN_AGENT = re.compile(r"(?P<run>[0-7][0-9A-HJKMNP-TV-Z]{25})/root(?:\.[1-9][0-9]*)*\Z")


class _RunAttempt(ContractModel):
    run_id: ULID
    origin_agent: NonBlankString

    @model_validator(mode="after")
    def require_materialized_path(self) -> _RunAttempt:
        match = _ORIGIN_AGENT.fullmatch(self.origin_agent)
        if match is None or match.group("run") != self.run_id:
            raise ValueError("origin_agent must be <run_id>/root[.<positive integer>...]")
        return self


class StageMemoryRequest(_RunAttempt):
    memory_id: UUID
    principal_id: NonBlankString
    label: NonBlankString
    body: NonBlankString
    kind: MemoryKind
    keywords: list[str] = Field(default_factory=list)
    project_key: str | None = None
    origin_thread_id: UUID
    origin_path: str | None = None
    machine_id: NonBlankString


class VisibilityRequest(_RunAttempt):
    principal_id: NonBlankString


class SymphonyMemoryRecord(ContractModel):
    memory_id: UUID
    principal_id: str
    label: str
    body: str
    kind: MemoryKind
    keywords: list[str]
    project_key: str | None
    origin_thread_id: UUID | None
    origin_path: str | None
    pin: bool
    status: Literal["active", "candidate", "staged", "quarantined", "tombstoned"]
    revision: int
    run_id: str | None
    origin_agent: str | None
    staged: bool
    created_at: datetime
    updated_at: datetime


class StageMemoryResponse(ContractModel):
    memory: SymphonyMemoryRecord


class VisibilityResponse(ContractModel):
    memories: list[SymphonyMemoryRecord]


class JudgedContext(ContractModel):
    verdict: Literal["unanimous_pass"]
    summary: NonBlankString
    judge_ids: list[NonBlankString] = Field(min_length=3)
    evidence_refs: list[NonBlankString] = Field(min_length=1)

    @model_validator(mode="after")
    def require_independent_judges(self) -> JudgedContext:
        if len(set(self.judge_ids)) != len(self.judge_ids):
            raise ValueError("judge_ids must be unique")
        return self


class ResolveRunRequest(ContractModel):
    principal_id: NonBlankString
    batch_uid: UUID
    winner_origin_agent: NonBlankString
    machine_id: NonBlankString
    judged_context: JudgedContext


class ResolveRunResponse(ContractModel):
    run_id: ULID
    batch_uid: UUID
    winner_origin_agent: str
    queue_cards: list[QueueCard]
    losers: list[SymphonyMemoryRecord]


def record_from_row(row: Mapping[str, Any]) -> SymphonyMemoryRecord:
    """Project a DB head without pretending staged status is an ordinary C.4 unit."""

    return SymphonyMemoryRecord(
        memory_id=row["id"],
        principal_id=row["principal_id"],
        label=row["label"],
        body=row["body"],
        kind=row["kind"],
        keywords=list(row["keywords"]),
        project_key=row["project_key"],
        origin_thread_id=row["origin_thread_id"],
        origin_path=row["origin_path"],
        pin=row["pin"],
        status=row["status"],
        revision=row["revision"],
        run_id=row["run_id"],
        origin_agent=row["origin_agent"],
        staged=row["status"] == "staged",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
