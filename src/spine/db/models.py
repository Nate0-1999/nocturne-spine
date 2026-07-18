"""Literal SQLAlchemy mappings for the authoritative SPEC C.2 DDL."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for the five C.2 tables."""


class MemoryUnit(Base):
    """The mutable cloud head for one atomic memory unit."""

    __tablename__ = "memory_unit"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('fact','preference','procedure','project_note','persona','pinned')",
            name="memory_unit_kind_check",
        ),
        CheckConstraint(
            "status IN ('active','quarantined','tombstoned')",
            name="memory_unit_status_check",
        ),
        Index(
            "memory_unit_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "memory_unit_principal_id_status_project_key_idx",
            "principal_id",
            "status",
            "project_key",
        ),
        Index(
            "memory_unit_active_label",
            "principal_id",
            "label",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    principal_id: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'"),
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    project_key: Mapped[str | None] = mapped_column(Text)
    thread_origin: Mapped[str | None] = mapped_column(Text)
    pin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text(
            '\'{"injections"\\:0,"removals"\\:0,"citations"\\:0,'
            '"never_kills"\\:0,"last_injected_at"\\:null}\'::jsonb'
        ),
    )
    bias: Mapped[float] = mapped_column(REAL, nullable=False, server_default=text("0.0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class MemoryRevision(Base):
    """One append-only memory head or divergent lineage revision."""

    __tablename__ = "memory_revision"
    __table_args__ = (Index("memory_revision_memory_id_ts_idx", "memory_id", "ts"),)

    rev_uid: Mapped[str] = mapped_column(Text, primary_key=True)
    parent_uid: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("memory_revision.rev_uid", name="memory_revision_parent_uid_fkey"),
    )
    memory_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("memory_unit.id", name="memory_revision_memory_id_fkey"),
        nullable=False,
    )
    revision: Mapped[int | None] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    editor: Mapped[str] = mapped_column(Text, nullable=False)
    origin_machine_id: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class Thread(Base):
    """Thread identity and its first-prepare memory snapshot boundary."""

    __tablename__ = "thread"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    principal_id: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    machine_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_key: Mapped[str | None] = mapped_column(Text)
    snapshot_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class InjectionEvent(Base):
    """Append-only injection decision and outcome event."""

    __tablename__ = "injection_event"
    __table_args__ = (
        CheckConstraint(
            "shown_as IN ('injected','near_miss','pinned')",
            name="injection_event_shown_as_check",
        ),
        UniqueConstraint("event_uid", name="injection_event_event_uid_key"),
        Index("injection_event_injection_id_idx", "injection_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_uid: Mapped[str] = mapped_column(Text, nullable=False)
    injection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    thread_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    machine_id: Mapped[str] = mapped_column(Text, nullable=False)
    principal_id: Mapped[str] = mapped_column(Text, nullable=False)
    project_key: Mapped[str | None] = mapped_column(Text)
    agent_kind: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'general'"),
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    scorer_version: Mapped[str] = mapped_column(Text, nullable=False)
    memory_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    memory_kind: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    score: Mapped[float] = mapped_column(REAL, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    shown_as: Mapped[str] = mapped_column(Text, nullable=False)
    outcome: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ScorerConfig(Base):
    """Versioned scorer weights and parameters."""

    __tablename__ = "scorer_config"

    version: Mapped[str] = mapped_column(Text, primary_key=True)
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
