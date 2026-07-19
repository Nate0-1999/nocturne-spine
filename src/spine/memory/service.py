"""Transactional memory CRUD and dedup behavior for SPEC C.4."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal
from uuid import UUID

from sqlalchemy import func, insert, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.contracts import (
    MemoryKind,
    MemoryListResponse,
    MemoryStatus,
    SimilarityMemoryCard,
)
from spine.contracts import (
    MemoryUnit as ContractMemoryUnit,
)
from spine.db.memory import (
    CasUpdate,
    MemoryUnitChanges,
    MemoryUnitSnapshot,
    cas_update_memory_unit,
)
from spine.db.memory import (
    MemoryCasConflictError as DatabaseCasConflictError,
)
from spine.db.memory import (
    MemoryUnitNotFoundError as DatabaseMemoryNotFoundError,
)
from spine.db.models import MemoryRevision, MemoryUnit
from spine.embeddings import (
    EmbeddingConfigurationError,
    EmbeddingProvider,
    embed_one,
)
from spine.ids import mint_ulid
from spine.tokens import cl100k_token_count

_EMBEDDING_DIMENSIONS = 1536
_ACTIVE_LABEL_CONSTRAINT = "memory_unit_active_label"


class UnsetType:
    """Sentinel type for mutable PATCH properties omitted by the caller."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateMemoryCommand:
    principal_id: str
    label: str
    body: str
    kind: MemoryKind
    editor: str
    machine_id: str
    keywords: Sequence[str] = ()
    project_key: str | None = None
    thread_origin: str | None = None
    force: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class PatchMemoryCommand:
    memory_id: UUID
    expected_revision: int
    editor: str
    reason: str
    machine_id: str
    body: str | None | UnsetType = UNSET
    label: str | None | UnsetType = UNSET
    keywords: Sequence[str] | None | UnsetType = UNSET
    kind: MemoryKind | None | UnsetType = UNSET
    pin: bool | None | UnsetType = UNSET
    status: MemoryStatus | None | UnsetType = UNSET


@dataclass(frozen=True, slots=True, kw_only=True)
class ListMemoriesQuery:
    project_key: str | None = None
    status: MemoryStatus | None = None
    q: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryCreated:
    memory: ContractMemoryUnit


@dataclass(frozen=True, slots=True, kw_only=True)
class SimilarMemories:
    similar: tuple[SimilarityMemoryCard, ...]


class MemoryServiceError(RuntimeError):
    """Base class for expected memory-domain failures."""


class LabelConflictError(MemoryServiceError):
    """An ACTIVE unit already owns the resulting principal/label pair."""

    def __init__(self, memory_id: UUID, label: str) -> None:
        self.memory_id = memory_id
        self.label = label
        super().__init__(f"active memory {memory_id} already uses label {label!r}")


class DuplicateMemoryError(MemoryServiceError):
    """A create request is at or above the hard-duplicate threshold."""

    def __init__(self, duplicate_of: SimilarityMemoryCard) -> None:
        self.duplicate_of = duplicate_of
        super().__init__(f"memory {duplicate_of.memory_id} is a hard duplicate")


class MemoryNotFoundError(MemoryServiceError):
    """The requested memory head does not exist."""

    def __init__(self, memory_id: UUID) -> None:
        self.memory_id = memory_id
        super().__init__(f"memory {memory_id} does not exist")


class RevisionConflictError(MemoryServiceError):
    """A PATCH expected a stale cloud-head revision."""

    def __init__(self, current: ContractMemoryUnit) -> None:
        self.current = current
        super().__init__(
            f"memory {current.memory_id} is at revision {current.revision}; PATCH was stale"
        )


class EmptyPatchError(MemoryServiceError):
    """A PATCH contains no non-null mutable properties."""


class InvalidListQueryError(MemoryServiceError):
    """List paging values fall outside the C.4 bounds."""


class MemoryValidationError(MemoryServiceError):
    """A memory label or body exceeds an enacted C.2/C.5 limit."""


class MemoryService:
    """Own C.4 memory transactions while keeping HTTP concerns in the router."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
        *,
        dedup_dup: float = 0.92,
        dedup_sim: float = 0.80,
        label_max: int = 64,
        memory_max_tokens: int = 128,
    ) -> None:
        if embedding_provider.dimensions != _EMBEDDING_DIMENSIONS:
            raise EmbeddingConfigurationError(
                f"memory_unit requires {_EMBEDDING_DIMENSIONS}-dimension embeddings; "
                f"provider supplies {embedding_provider.dimensions}"
            )
        if not 0.0 <= dedup_sim < dedup_dup <= 1.0:
            raise ValueError("dedup thresholds must satisfy 0 <= dedup_sim < dedup_dup <= 1")
        if label_max <= 0 or memory_max_tokens <= 0:
            raise ValueError("memory limits must be positive")

        self._session_factory = session_factory
        self._embedding_provider = embedding_provider
        self._dedup_dup = dedup_dup
        self._dedup_sim = dedup_sim
        self._label_max = label_max
        self._memory_max_tokens = memory_max_tokens

    async def create(
        self,
        command: CreateMemoryCommand,
    ) -> MemoryCreated | SimilarMemories:
        """Create a root head/revision or return the exact dedup-band outcome."""

        self._validate_label(command.label)

        # C.4 deliberately puts the cheap active-label check before provider I/O.
        async with self._session_factory() as preflight_session:
            conflict = await _find_active_label(
                preflight_session,
                principal_id=command.principal_id,
                label=command.label,
            )
        if conflict is not None:
            raise LabelConflictError(conflict["id"], conflict["label"])

        self._validate_body(command.body)
        embedding = await embed_one(
            self._embedding_provider,
            command.body,
            expected_dimensions=_EMBEDDING_DIMENSIONS,
        )

        async with self._session_factory() as session:
            async with session.begin():
                # Serialize the authoritative recheck, dedup read, and root insert for
                # one principal. Different principals remain independent.
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtextextended(:principal_id, 0))"),
                    {"principal_id": command.principal_id},
                )

                conflict = await _find_active_label(
                    session,
                    principal_id=command.principal_id,
                    label=command.label,
                )
                if conflict is not None:
                    raise LabelConflictError(conflict["id"], conflict["label"])

                matches = await self._dedup_matches(
                    session,
                    principal_id=command.principal_id,
                    embedding=embedding,
                )
                highest_score = matches[0].score if matches else None
                band = _classify_dedup_score(
                    highest_score,
                    dedup_sim=self._dedup_sim,
                    dedup_dup=self._dedup_dup,
                )
                if band == "duplicate":
                    raise DuplicateMemoryError(matches[0])
                if band == "similar" and not command.force:
                    return SimilarMemories(similar=tuple(matches))

                try:
                    async with session.begin_nested():
                        row = await self._insert_root(session, command, embedding)
                except IntegrityError as error:
                    # The advisory lock closes service-to-service create races. Keep
                    # the partial unique index authoritative for out-of-band writers.
                    if _integrity_constraint_name(error) != _ACTIVE_LABEL_CONSTRAINT:
                        raise
                    conflict = await _find_active_label(
                        session,
                        principal_id=command.principal_id,
                        label=command.label,
                    )
                    if conflict is not None:
                        raise LabelConflictError(conflict["id"], conflict["label"]) from None
                    raise

                return MemoryCreated(memory=_contract_memory_from_row(row))

    async def patch(self, command: PatchMemoryCommand) -> ContractMemoryUnit:
        """CAS-update a head and append its resulting cloud revision."""

        if not any(
            _provided(value)
            for value in (
                command.body,
                command.label,
                command.keywords,
                command.kind,
                command.pin,
                command.status,
            )
        ):
            raise EmptyPatchError("PATCH requires at least one non-null mutable property")

        # C.2 forbids hard deletion, so this preflight gives A-004's missing-ID
        # response precedence without weakening the later revision CAS.
        async with self._session_factory() as preflight_session:
            exists = await preflight_session.scalar(
                select(MemoryUnit.id).where(MemoryUnit.id == command.memory_id)
            )
        if exists is None:
            raise MemoryNotFoundError(command.memory_id)

        if _provided(command.body):
            self._validate_body(command.body)
        if _provided(command.label):
            self._validate_label(command.label)

        change_values: dict[str, Any] = {}
        if _provided(command.body):
            embedding = await embed_one(
                self._embedding_provider,
                command.body,
                expected_dimensions=_EMBEDDING_DIMENSIONS,
            )
            change_values.update(
                body=command.body,
                embedding=embedding,
                embedding_model=self._embedding_provider.model,
            )
        if _provided(command.label):
            change_values["label"] = command.label
        if _provided(command.keywords):
            change_values["keywords"] = tuple(command.keywords)
        if _provided(command.kind):
            change_values["kind"] = command.kind
        if _provided(command.pin):
            change_values["pin"] = command.pin
        if _provided(command.status):
            change_values["status"] = command.status

        async with self._session_factory() as session:
            async with session.begin():
                try:
                    snapshot = await cas_update_memory_unit(
                        session,
                        CasUpdate(
                            memory_id=command.memory_id,
                            expected_revision=command.expected_revision,
                            rev_uid=mint_ulid(),
                            editor=command.editor,
                            origin_machine_id=command.machine_id,
                            reason=command.reason,
                            changes=MemoryUnitChanges(**change_values),
                        ),
                    )
                except DatabaseMemoryNotFoundError as error:
                    raise MemoryNotFoundError(error.memory_id) from None
                except DatabaseCasConflictError as error:
                    current = _contract_memory_from_snapshot(error.current)
                    raise RevisionConflictError(current) from None
                except IntegrityError as error:
                    if _integrity_constraint_name(error) != _ACTIVE_LABEL_CONSTRAINT:
                        raise
                    conflict = await _patch_label_conflict(session, command, change_values)
                    if conflict is not None:
                        raise LabelConflictError(conflict["id"], conflict["label"]) from None
                    raise

                return _contract_memory_from_snapshot(snapshot)

    async def list(self, query: ListMemoriesQuery) -> MemoryListResponse:
        """List heads with literal filters, stable ordering, and filtered count."""

        if isinstance(query.limit, bool) or not 1 <= query.limit <= 200:
            raise InvalidListQueryError("limit must satisfy 1 <= limit <= 200")
        if isinstance(query.offset, bool) or query.offset < 0:
            raise InvalidListQueryError("offset must be greater than or equal to zero")

        unit = MemoryUnit.__table__
        filters = []
        if query.project_key is not None:
            filters.append(unit.c.project_key == query.project_key)
        if query.status is not None:
            filters.append(unit.c.status == query.status)
        if query.q is not None and (term := query.q.strip()):
            pattern = f"%{_escape_ilike(term)}%"
            filters.append(
                or_(
                    unit.c.label.ilike(pattern, escape="\\"),
                    unit.c.body.ilike(pattern, escape="\\"),
                )
            )

        async with self._session_factory() as session:
            total = await session.scalar(select(func.count()).select_from(unit).where(*filters))
            rows = (
                (
                    await session.execute(
                        select(*unit.c)
                        .where(*filters)
                        .order_by(unit.c.updated_at.desc(), unit.c.id.asc())
                        .limit(query.limit)
                        .offset(query.offset)
                    )
                )
                .mappings()
                .all()
            )

        return MemoryListResponse(
            items=[_contract_memory_from_row(row) for row in rows],
            total=int(total or 0),
            limit=query.limit,
            offset=query.offset,
        )

    def _validate_label(self, label: str) -> None:
        if len(label) > self._label_max:
            raise MemoryValidationError(
                f"label has {len(label)} Unicode code points; maximum is {self._label_max}"
            )

    def _validate_body(self, body: str) -> None:
        tokens = cl100k_token_count(body)
        if tokens > self._memory_max_tokens:
            raise MemoryValidationError(
                f"body has {tokens} cl100k_base tokens; maximum is {self._memory_max_tokens}"
            )

    async def _dedup_matches(
        self,
        session: AsyncSession,
        *,
        principal_id: str,
        embedding: Sequence[float],
    ) -> list[SimilarityMemoryCard]:
        unit = MemoryUnit.__table__
        cosine_score = (1.0 - unit.c.embedding.cosine_distance(list(embedding))).label("score")
        rows = (
            (
                await session.execute(
                    select(*unit.c, cosine_score)
                    .where(
                        unit.c.principal_id == principal_id,
                        unit.c.status == "active",
                        cosine_score >= self._dedup_sim,
                    )
                    .order_by(cosine_score.desc(), unit.c.id.asc())
                )
            )
            .mappings()
            .all()
        )
        return [_similarity_card_from_row(row) for row in rows]

    async def _insert_root(
        self,
        session: AsyncSession,
        command: CreateMemoryCommand,
        embedding: Sequence[float],
    ) -> Mapping[str, Any]:
        unit = MemoryUnit.__table__
        row = (
            (
                await session.execute(
                    insert(unit)
                    .values(
                        principal_id=command.principal_id,
                        label=command.label,
                        body=command.body,
                        kind=command.kind,
                        keywords=list(command.keywords),
                        embedding=list(embedding),
                        embedding_model=self._embedding_provider.model,
                        project_key=command.project_key,
                        thread_origin=command.thread_origin,
                        pin=False,
                        status="active",
                        revision=1,
                    )
                    .returning(*unit.c)
                )
            )
            .mappings()
            .one()
        )
        await session.execute(
            insert(MemoryRevision.__table__).values(
                rev_uid=mint_ulid(),
                parent_uid=None,
                memory_id=row["id"],
                revision=1,
                body=row["body"],
                label=row["label"],
                editor=command.editor,
                origin_machine_id=command.machine_id,
                reason="",
            )
        )
        return row


async def _find_active_label(
    session: AsyncSession,
    *,
    principal_id: str,
    label: str,
    exclude_memory_id: UUID | None = None,
) -> Mapping[str, Any] | None:
    unit = MemoryUnit.__table__
    filters = [
        unit.c.principal_id == principal_id,
        unit.c.label == label,
        unit.c.status == "active",
    ]
    if exclude_memory_id is not None:
        filters.append(unit.c.id != exclude_memory_id)
    return (
        (
            await session.execute(
                select(unit.c.id, unit.c.label).where(*filters).order_by(unit.c.id.asc()).limit(1)
            )
        )
        .mappings()
        .one_or_none()
    )


async def _patch_label_conflict(
    session: AsyncSession,
    command: PatchMemoryCommand,
    change_values: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    unit = MemoryUnit.__table__
    current = (
        (await session.execute(select(*unit.c).where(unit.c.id == command.memory_id)))
        .mappings()
        .one_or_none()
    )
    if current is None:
        return None
    resulting_status = change_values.get("status", current["status"])
    if resulting_status != "active":
        return None
    return await _find_active_label(
        session,
        principal_id=current["principal_id"],
        label=change_values.get("label", current["label"]),
        exclude_memory_id=command.memory_id,
    )


def _contract_memory_from_snapshot(snapshot: MemoryUnitSnapshot) -> ContractMemoryUnit:
    return ContractMemoryUnit(
        memory_id=snapshot.id,
        principal_id=snapshot.principal_id,
        label=snapshot.label,
        body=snapshot.body,
        kind=snapshot.kind,
        keywords=list(snapshot.keywords),
        project_key=snapshot.project_key,
        thread_origin=snapshot.thread_origin,
        pin=snapshot.pin,
        status=snapshot.status,
        revision=snapshot.revision,
        stats=snapshot.stats,
        bias=snapshot.bias,
        embedding_model=snapshot.embedding_model,
        created_at=snapshot.created_at,
        updated_at=snapshot.updated_at,
    )


def _contract_memory_from_row(row: Mapping[str, Any]) -> ContractMemoryUnit:
    return _contract_memory_from_snapshot(MemoryUnitSnapshot.from_row(row))


def _similarity_card_from_row(row: Mapping[str, Any]) -> SimilarityMemoryCard:
    return SimilarityMemoryCard(
        memory_id=row["id"],
        label=row["label"],
        body=row["body"],
        kind=row["kind"],
        pin=row["pin"],
        score=float(row["score"]),
        features=None,
        rank=None,
    )


def _provided(value: object) -> bool:
    return value is not UNSET and value is not None


def _classify_dedup_score(
    score: float | None,
    *,
    dedup_sim: float,
    dedup_dup: float,
) -> Literal["distinct", "similar", "duplicate"]:
    if score is None or score < dedup_sim:
        return "distinct"
    if score < dedup_dup:
        return "similar"
    return "duplicate"


def _escape_ilike(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _integrity_constraint_name(error: IntegrityError) -> str | None:
    candidate: object | None = error.orig
    for _ in range(2):
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str):
            return name
        candidate = getattr(candidate, "__cause__", None)
    return None


__all__ = [
    "CreateMemoryCommand",
    "DuplicateMemoryError",
    "EmptyPatchError",
    "InvalidListQueryError",
    "LabelConflictError",
    "ListMemoriesQuery",
    "MemoryCreated",
    "MemoryNotFoundError",
    "MemoryService",
    "MemoryServiceError",
    "MemoryValidationError",
    "PatchMemoryCommand",
    "RevisionConflictError",
    "SimilarMemories",
    "UNSET",
    "UnsetType",
]
