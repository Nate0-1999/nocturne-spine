"""Wire contracts for exact append-only transcript backup."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    model_validator,
)


def _nonblank(value: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError("value must be nonblank without surrounding whitespace")
    return value


type NonBlankString = Annotated[StrictStr, AfterValidator(_nonblank)]
type PositiveInt = Annotated[StrictInt, Field(gt=0)]


class TranscriptContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TranscriptRecordInput(TranscriptContract):
    thread_id: UUID
    sequence: PositiveInt
    journal_line: StrictStr
    sha256: Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def exact_valid_journal_line(self) -> TranscriptRecordInput:
        if "\n" in self.journal_line or "\r" in self.journal_line:
            raise ValueError("journal_line must be one JSON line without a newline")
        if hashlib.sha256(self.journal_line.encode("utf-8")).hexdigest() != self.sha256:
            raise ValueError("sha256 does not match journal_line")
        try:
            value = json.loads(self.journal_line)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("journal_line must contain valid JSON") from error
        if not isinstance(value, dict):
            raise ValueError("journal_line must contain a JSON object")
        if value.get("thread_id") != str(self.thread_id):
            raise ValueError("journal_line thread_id does not match record thread_id")
        captured_at = value.get("captured_at")
        if not isinstance(captured_at, str):
            raise ValueError("journal_line captured_at must be an aware timestamp")
        from datetime import datetime

        try:
            parsed = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("journal_line captured_at must be an aware timestamp") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("journal_line captured_at must be an aware timestamp")
        return self


class AppendTranscriptsRequest(TranscriptContract):
    principal_id: NonBlankString
    records: Annotated[list[TranscriptRecordInput], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def unique_ordered_records(self) -> AppendTranscriptsRequest:
        keys = [(record.thread_id, record.sequence) for record in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError("records must have unique thread_id and sequence keys")
        if keys != sorted(keys, key=lambda key: (str(key[0]), key[1])):
            raise ValueError("records must be ordered by thread_id and sequence")
        return self


class TranscriptRecordView(TranscriptContract):
    thread_id: UUID
    sequence: PositiveInt
    journal_line: str
    sha256: str
    received_at: AwareDatetime


class TranscriptAppendResult(TranscriptContract):
    accepted: int
    replayed: int
    status: TranscriptStatus


class TranscriptList(TranscriptContract):
    principal_id: NonBlankString
    records: list[TranscriptRecordView]


class TranscriptStatus(TranscriptContract):
    principal_id: NonBlankString
    thread_count: int
    record_count: int
    latest_received_at: AwareDatetime | None
