"""Pure deterministic fit and replay math for the M2F Chrysopoeia learner."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

FEATURE_NAMES = ("sem", "kw", "time", "proj", "freq", "hist")
EXPLICIT_POSITIVE_OUTCOMES = frozenset({"added_back", "cited", "mid_thread_added"})
NEGATIVE_OUTCOMES = frozenset(
    {"removed:not_relevant", "removed:never", "mid_thread_removed"}
)
PASSIVE_POSITIVE_OUTCOMES = frozenset({"kept", "auto_entered"})


@dataclass(frozen=True, slots=True, kw_only=True)
class LearningExample:
    """One hygiene-passing disposition with its frozen replay inputs."""

    event_uid: str
    injection_id: UUID
    memory_id: UUID
    ts: datetime
    features: tuple[float, float, float, float, float, float]
    baseline_bias: float
    target_injected: bool
    actor_weight: Decimal
    shown_as: Literal["injected", "near_miss", "pinned"]
    body_tokens: int

    @property
    def recorded_injected(self) -> bool:
        return self.shown_as != "near_miss"


@dataclass(frozen=True, slots=True, kw_only=True)
class FitSettings:
    pair_margin: float
    bias_l2: float


@dataclass(frozen=True, slots=True, kw_only=True)
class FitResult:
    weights: tuple[float, float, float, float, float, float]
    bias_offsets: Mapping[UUID, float]
    pair_count: int
    iterations: int
    objective: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplayScore:
    disagreements: int
    weighted_disagreements: Decimal
    injected_tokens: int


def disposition(
    outcome: str | None,
    actor_class: str,
    *,
    passive_discount: Decimal,
) -> tuple[bool, Decimal] | None:
    """Map one stored outcome to A-031's binary label and actor weight."""

    if outcome in EXPLICIT_POSITIVE_OUTCOMES:
        return True, Decimal(1)
    if outcome in NEGATIVE_OUTCOMES:
        return False, Decimal(1)
    if actor_class == "human":
        if outcome == "kept":
            return True, Decimal(1)
        return None
    if actor_class == "passive" and outcome in PASSIVE_POSITIVE_OUTCOMES:
        return True, passive_discount
    return None


def identity_is_excluded(*, principal_id: str, machine_id: str) -> bool:
    """Recognize the enacted fixture/test/verification identity classes."""

    return _identity_value_is_excluded(principal_id) or _identity_value_is_excluded(machine_id)


def split_gates(
    examples: Sequence[LearningExample],
    *,
    holdout_fraction: float,
) -> tuple[tuple[LearningExample, ...], tuple[LearningExample, ...], datetime]:
    """Create one deterministic newest-gates holdout without row leakage."""

    grouped: dict[UUID, list[LearningExample]] = defaultdict(list)
    for example in examples:
        grouped[example.injection_id].append(example)
    gates = sorted(
        grouped.items(),
        key=lambda item: (max(example.ts for example in item[1]), item[0].int),
    )
    if len(gates) < 2:
        raise ValueError("at least two eligible gates are required")
    holdout_count = max(1, math.ceil(len(gates) * holdout_fraction))
    holdout_count = min(holdout_count, len(gates) - 1)
    training_gates = gates[:-holdout_count]
    holdout_gates = gates[-holdout_count:]
    training = tuple(example for _, rows in training_gates for example in rows)
    holdout = tuple(example for _, rows in holdout_gates for example in rows)
    cutoff = max(example.ts for example in training)
    return training, holdout, cutoff


def fit_pairwise(
    examples: Sequence[LearningExample],
    *,
    incumbent_weights: Sequence[float],
    settings: FitSettings,
) -> FitResult:
    """Solve the full convex squared-hinge objective by projected gradient."""

    if len(incumbent_weights) != len(FEATURE_NAMES):
        raise ValueError("incumbent weights must have six values")
    weights = _project_simplex(tuple(float(value) for value in incumbent_weights))
    pairs = _pairs(examples)
    if not pairs:
        raise ValueError("at least one positive-negative training pair is required")
    memory_ids = sorted(
        {example.memory_id for pair in pairs for example in pair[:2]}, key=lambda item: item.int
    )
    biases = {memory_id: 0.0 for memory_id in memory_ids}
    lipschitz = 2.0 * settings.bias_l2
    for positive, negative, actor_weight in pairs:
        feature_delta = tuple(
            left - right for left, right in zip(positive.features, negative.features, strict=True)
        )
        pair_norm = math.fsum(value * value for value in feature_delta) + 2.0
        lipschitz += 2.0 * actor_weight * pair_norm
    step = 1.0 / max(lipschitz, 1.0)
    objective = math.inf
    iterations = 0
    for iteration in range(1, 10_001):
        iterations = iteration
        current_objective, weight_gradient, bias_gradient = _objective_and_gradient(
            weights,
            biases,
            pairs,
            settings=settings,
        )
        next_weights = _project_simplex(
            tuple(
                value - step * gradient
                for value, gradient in zip(weights, weight_gradient, strict=True)
            )
        )
        next_biases = {
            memory_id: biases[memory_id] - step * bias_gradient[memory_id]
            for memory_id in memory_ids
        }
        next_objective = _objective(next_weights, next_biases, pairs, settings=settings)
        change = max(
            max(abs(left - right) for left, right in zip(weights, next_weights, strict=True)),
            max(abs(biases[item] - next_biases[item]) for item in memory_ids),
        )
        improvement = current_objective - next_objective
        weights = next_weights
        biases = next_biases
        objective = next_objective
        if change <= 1e-11 or (0.0 <= improvement <= 1e-13):
            break
    normalized_biases = {
        memory_id: value for memory_id, value in biases.items() if abs(value) > 1e-12
    }
    return FitResult(
        weights=weights,
        bias_offsets=normalized_biases,
        pair_count=len(pairs),
        iterations=iterations,
        objective=objective,
    )


def recorded_score(examples: Iterable[LearningExample]) -> ReplayScore:
    """Score the incumbent decisions that actually served the held-out gates."""

    return _replay_score(
        examples,
        predicted=lambda example: example.recorded_injected,
    )


def challenger_score(
    examples: Iterable[LearningExample],
    *,
    weights: Sequence[float],
    bias_offsets: Mapping[UUID, float],
    tau: float,
) -> ReplayScore:
    """Score one fitted challenger against the held-out binary dispositions."""

    def predicted(example: LearningExample) -> bool:
        if example.shown_as == "pinned":
            return True
        score = math.fsum(
            weight * feature for weight, feature in zip(weights, example.features, strict=True)
        )
        score += example.baseline_bias + bias_offsets.get(example.memory_id, 0.0)
        return score >= tau

    return _replay_score(examples, predicted=predicted)


def challenger_wins(
    incumbent: ReplayScore,
    challenger: ReplayScore,
    *,
    margin: Decimal,
) -> bool:
    """Apply the real-margin rule, then the exact cheaper-at-tie exception."""

    improvement = incumbent.weighted_disagreements - challenger.weighted_disagreements
    if improvement >= margin:
        return True
    return improvement == 0 and challenger.injected_tokens < incumbent.injected_tokens


def canonical_digest(
    *,
    incumbent_version: str,
    training: Sequence[LearningExample],
    holdout: Sequence[LearningExample],
    settings: Mapping[str, object],
) -> str:
    """Hash every authority input used by a proposal in canonical order."""

    payload = {
        "incumbent_version": incumbent_version,
        "training": [_canonical_example(item) for item in training],
        "holdout": [_canonical_example(item) for item in holdout],
        "settings": settings,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _pairs(
    examples: Sequence[LearningExample],
) -> tuple[tuple[LearningExample, LearningExample, float], ...]:
    grouped: dict[UUID, list[LearningExample]] = defaultdict(list)
    for example in examples:
        grouped[example.injection_id].append(example)
    pairs: list[tuple[LearningExample, LearningExample, float]] = []
    for injection_id in sorted(grouped, key=lambda item: item.int):
        rows = grouped[injection_id]
        positives = sorted(
            (row for row in rows if row.target_injected), key=lambda item: item.event_uid
        )
        negatives = sorted(
            (row for row in rows if not row.target_injected), key=lambda item: item.event_uid
        )
        for positive in positives:
            for negative in negatives:
                pairs.append(
                    (
                        positive,
                        negative,
                        float(min(positive.actor_weight, negative.actor_weight)),
                    )
                )
    return tuple(pairs)


def _objective_and_gradient(
    weights: Sequence[float],
    biases: Mapping[UUID, float],
    pairs: Sequence[tuple[LearningExample, LearningExample, float]],
    *,
    settings: FitSettings,
) -> tuple[float, list[float], dict[UUID, float]]:
    weight_gradient = [0.0] * len(FEATURE_NAMES)
    bias_gradient = {
        memory_id: 2.0 * settings.bias_l2 * value
        for memory_id, value in biases.items()
    }
    objective = settings.bias_l2 * math.fsum(value * value for value in biases.values())
    for positive, negative, actor_weight in pairs:
        feature_delta = tuple(
            left - right for left, right in zip(positive.features, negative.features, strict=True)
        )
        difference = math.fsum(
            weight * delta for weight, delta in zip(weights, feature_delta, strict=True)
        )
        difference += positive.baseline_bias - negative.baseline_bias
        difference += biases[positive.memory_id] - biases[negative.memory_id]
        hinge = settings.pair_margin - difference
        if hinge <= 0.0:
            continue
        objective += actor_weight * hinge * hinge
        factor = -2.0 * actor_weight * hinge
        for index, delta in enumerate(feature_delta):
            weight_gradient[index] += factor * delta
        bias_gradient[positive.memory_id] += factor
        bias_gradient[negative.memory_id] -= factor
    return objective, weight_gradient, bias_gradient


def _objective(
    weights: Sequence[float],
    biases: Mapping[UUID, float],
    pairs: Sequence[tuple[LearningExample, LearningExample, float]],
    *,
    settings: FitSettings,
) -> float:
    return _objective_and_gradient(weights, biases, pairs, settings=settings)[0]


def _project_simplex(values: Sequence[float]) -> tuple[float, ...]:
    """Euclidean projection onto non-negative values summing exactly to one."""

    ordered = sorted((float(value) for value in values), reverse=True)
    cumulative = 0.0
    rho = 0
    for index, value in enumerate(ordered, start=1):
        cumulative += value
        if value - (cumulative - 1.0) / index > 0.0:
            rho = index
    if rho == 0:
        return tuple(1.0 / len(values) for _ in values)
    theta = (math.fsum(ordered[:rho]) - 1.0) / rho
    projected = [max(float(value) - theta, 0.0) for value in values]
    total = math.fsum(projected)
    normalized = [value / total for value in projected]
    normalized[-1] += 1.0 - math.fsum(normalized)
    return tuple(normalized)


def _replay_score(
    examples: Iterable[LearningExample],
    *,
    predicted,
) -> ReplayScore:
    disagreements = 0
    weighted_disagreements = Decimal(0)
    injected_tokens = 0
    for example in examples:
        prediction = bool(predicted(example))
        if prediction:
            injected_tokens += example.body_tokens
        if prediction != example.target_injected:
            disagreements += 1
            weighted_disagreements += example.actor_weight
    return ReplayScore(
        disagreements=disagreements,
        weighted_disagreements=weighted_disagreements,
        injected_tokens=injected_tokens,
    )


def _identity_value_is_excluded(value: str) -> bool:
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"test", "fixture", "verification"}:
        return True
    tokens = tuple(part for part in normalized.replace(":", "-").split("-") if part)
    return any(token in {"test", "fixture", "verification"} for token in tokens)


def _canonical_example(example: LearningExample) -> dict[str, object]:
    return {
        "event_uid": example.event_uid,
        "injection_id": str(example.injection_id),
        "memory_id": str(example.memory_id),
        "ts": example.ts.isoformat(),
        "features": list(example.features),
        "baseline_bias": example.baseline_bias,
        "target_injected": example.target_injected,
        "actor_weight": str(example.actor_weight),
        "shown_as": example.shown_as,
        "body_tokens": example.body_tokens,
    }
