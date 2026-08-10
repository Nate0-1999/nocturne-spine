"""Atomic append-only A-053 injection-event hygiene annotations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.contracts import InjectionEventAnnotationInput
from spine.db.models import InjectionEvent, InjectionEventAnnotation
from spine.learner.locking import LEARNER_ADVISORY_LOCK_KEY

_VERIFICATION_ONLY = "verification_only"


class AnnotationTargetNotFoundError(RuntimeError):
    """A requested target event does not exist."""

    def __init__(self, target_event_uid: str) -> None:
        self.target_event_uid = target_event_uid
        super().__init__(f"injection event {target_event_uid} does not exist")


class AnnotationFingerprintMismatchError(RuntimeError):
    """The supplied target identities do not match the immutable event."""

    def __init__(self, target_event_uid: str) -> None:
        self.target_event_uid = target_event_uid
        super().__init__(f"injection event {target_event_uid} fingerprint does not match")


class AnnotationConflictError(RuntimeError):
    """A target was already annotated with different immutable fields."""

    def __init__(self, target_event_uid: str) -> None:
        self.target_event_uid = target_event_uid
        super().__init__(f"injection event {target_event_uid} annotation conflicts")


class InjectionEventAnnotationService:
    """Validate and append one atomic, replay-safe verification-only batch."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def append(self, annotations: Sequence[InjectionEventAnnotationInput]) -> int:
        """Persist all annotations or none, including exact replays in the count."""

        if not annotations:
            raise ValueError("injection event annotation batch must not be empty")
        target_uids = [annotation.target_event_uid for annotation in annotations]
        if len(set(target_uids)) != len(target_uids):
            raise ValueError("injection event annotation targets must be unique")

        async with self._session_factory() as session:
            async with session.begin():
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"),
                    {"key": LEARNER_ADVISORY_LOCK_KEY},
                )
                targets = (
                    (
                        await session.execute(
                            select(InjectionEvent).where(InjectionEvent.event_uid.in_(target_uids))
                        )
                    )
                    .scalars()
                    .all()
                )
                targets_by_uid = {target.event_uid: target for target in targets}
                for annotation in annotations:
                    target = targets_by_uid.get(annotation.target_event_uid)
                    if target is None:
                        raise AnnotationTargetNotFoundError(annotation.target_event_uid)
                    if (
                        target.principal_id != annotation.expected_principal_id
                        or target.machine_id != annotation.expected_machine_id
                    ):
                        raise AnnotationFingerprintMismatchError(annotation.target_event_uid)

                existing = (
                    (
                        await session.execute(
                            select(InjectionEventAnnotation).where(
                                InjectionEventAnnotation.target_event_uid.in_(target_uids)
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                existing_by_uid = {row.target_event_uid: row for row in existing}
                pending: list[InjectionEventAnnotation] = []
                for annotation in annotations:
                    target = targets_by_uid[annotation.target_event_uid]
                    values = _annotation_values(annotation, target)
                    row = existing_by_uid.get(annotation.target_event_uid)
                    if row is not None:
                        if _row_values(row) != values:
                            raise AnnotationConflictError(annotation.target_event_uid)
                        continue
                    pending.append(InjectionEventAnnotation(**values))
                session.add_all(pending)
        return len(annotations)


def _annotation_values(
    annotation: InjectionEventAnnotationInput,
    target: InjectionEvent,
) -> dict[str, Any]:
    return {
        "target_event_uid": target.event_uid,
        "kind": _VERIFICATION_ONLY,
        "target_principal_id": target.principal_id,
        "target_machine_id": target.machine_id,
        "reason": annotation.reason,
        "annotator_principal_id": annotation.annotator_principal_id,
        "annotator_machine_id": annotation.annotator_machine_id,
        "annotator_origin_agent": annotation.annotator_origin_agent,
    }


def _row_values(row: InjectionEventAnnotation) -> dict[str, Any]:
    return {
        "target_event_uid": row.target_event_uid,
        "kind": row.kind,
        "target_principal_id": row.target_principal_id,
        "target_machine_id": row.target_machine_id,
        "reason": row.reason,
        "annotator_principal_id": row.annotator_principal_id,
        "annotator_machine_id": row.annotator_machine_id,
        "annotator_origin_agent": row.annotator_origin_agent,
    }


__all__ = [
    "AnnotationConflictError",
    "AnnotationFingerprintMismatchError",
    "AnnotationTargetNotFoundError",
    "InjectionEventAnnotationService",
]
