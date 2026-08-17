"""Canonical A-031 evidence projection shared by retraining and read models."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from spine.db.models import InjectionEvent, InjectionEventAnnotation
from spine.inject.scorer import ScorerConfig as RuntimeScorerConfig
from spine.learner.model import (
    FEATURE_NAMES,
    LearningExample,
    disposition,
    identity_is_excluded,
)
from spine.tokens import cl100k_token_count


class LearnerDataError(RuntimeError):
    """The append-only evidence cannot be replayed without guessing."""


@dataclass(frozen=True, slots=True)
class LearningEvidence:
    examples: tuple[LearningExample, ...]
    hygiene_excluded_dispositions: int


def project_learning_evidence(
    rows: list[InjectionEvent],
    annotations: list[InjectionEventAnnotation],
    configs: Mapping[str, RuntimeScorerConfig],
    *,
    passive_discount: Decimal,
) -> LearningEvidence:
    """Apply A-031 grading and whole-gate hygiene exactly once for all consumers."""

    grouped: dict[UUID, list[InjectionEvent]] = defaultdict(list)
    for row in rows:
        grouped[row.injection_id].append(row)
    verification_only = {
        annotation.target_event_uid
        for annotation in annotations
        if annotation.kind == "verification_only"
    }
    excluded = {
        injection_id
        for injection_id, members in grouped.items()
        if any(
            member.event_uid in verification_only
            or identity_is_excluded(principal_id=member.principal_id, machine_id=member.machine_id)
            for member in members
        )
    }
    excluded_dispositions = sum(
        disposition(row.outcome, row.actor_class, passive_discount=passive_discount) is not None
        for row in rows
        if row.injection_id in excluded
    )
    examples: list[LearningExample] = []
    for row in rows:
        if row.injection_id in excluded:
            continue
        labeled = disposition(
            row.outcome,
            row.actor_class,
            passive_discount=passive_discount,
        )
        if labeled is None:
            continue
        source = configs.get(row.scorer_version)
        if source is None:
            raise LearnerDataError(
                f"event {row.event_uid} references missing scorer {row.scorer_version!r}"
            )
        features = _features(row, source)
        baseline_bias = float(row.score) - math.fsum(
            weight * feature
            for weight, feature in zip(_weight_tuple(source), features, strict=True)
        )
        baseline_bias -= source.bias_offset(row.memory_id)
        body = _frozen_body(row)
        target_injected, actor_weight = labeled
        examples.append(
            LearningExample(
                event_uid=row.event_uid,
                injection_id=row.injection_id,
                memory_id=row.memory_id,
                ts=row.ts,
                features=features,
                baseline_bias=baseline_bias,
                target_injected=target_injected,
                actor_weight=actor_weight,
                shown_as=row.shown_as,  # type: ignore[arg-type]
                body_tokens=cl100k_token_count(body),
            )
        )
    return LearningEvidence(
        examples=tuple(examples),
        hygiene_excluded_dispositions=excluded_dispositions,
    )


def _features(
    row: InjectionEvent,
    source: RuntimeScorerConfig,
) -> tuple[float, float, float, float, float, float]:
    values: list[float] = []
    for name in FEATURE_NAMES:
        value = row.features.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise LearnerDataError(f"event {row.event_uid} feature {name} is not numeric")
        normalized = float(value)
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise LearnerDataError(f"event {row.event_uid} feature {name} is outside [0,1]")
        values.append(normalized)
    location = row.features.get("loc")
    if isinstance(location, (int, float)) and not isinstance(location, bool):
        values = [value * (1.0 - source.params.location_weight) for value in values]
    return tuple(values)  # type: ignore[return-value]


def _frozen_body(row: InjectionEvent) -> str:
    memory = row.features.get("_memory")
    body = memory.get("body") if isinstance(memory, Mapping) else None
    if not isinstance(body, str):
        raise LearnerDataError(f"event {row.event_uid} has no frozen memory body")
    return body


def _weight_tuple(
    config: RuntimeScorerConfig,
) -> tuple[float, float, float, float, float, float]:
    weights = config.weights
    return (weights.sem, weights.kw, weights.time, weights.proj, weights.freq, weights.hist)


__all__ = [
    "LearnerDataError",
    "LearningEvidence",
    "project_learning_evidence",
]
