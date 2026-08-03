"""Golden tests for M2F's pure fit, hygiene, split, and binary referee."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from spine.learner.model import (
    FitSettings,
    LearningExample,
    ReplayScore,
    challenger_score,
    challenger_wins,
    disposition,
    fit_pairwise,
    identity_is_excluded,
    recorded_score,
    split_gates,
)

BASE = datetime(2026, 8, 3, tzinfo=UTC)
POSITIVE_ID = UUID("00000000-0000-0000-0000-000000000001")
NEGATIVE_ID = UUID("00000000-0000-0000-0000-000000000002")


def _example(
    *,
    event: int,
    gate: int,
    memory_id: UUID,
    sem: float,
    target: bool,
    shown_as: str,
    actor_weight: Decimal = Decimal(1),
) -> LearningExample:
    return LearningExample(
        event_uid=f"event-{event:02d}",
        injection_id=UUID(int=gate),
        memory_id=memory_id,
        ts=BASE + timedelta(hours=gate),
        features=(sem, 0.0, 0.0, 0.0, 0.0, 0.0),
        baseline_bias=0.0,
        target_injected=target,
        actor_weight=actor_weight,
        shown_as=shown_as,  # type: ignore[arg-type]
        body_tokens=event,
    )


def test_disposition_and_hygiene_are_actor_classed_without_self_training() -> None:
    discount = Decimal("0.25")

    assert disposition("kept", "human", passive_discount=discount) == (
        True,
        Decimal(1),
    )
    assert disposition("removed:never", "human", passive_discount=discount) == (
        False,
        Decimal(1),
    )
    assert disposition("auto_entered", "passive", passive_discount=discount) == (
        True,
        discount,
    )
    assert disposition("mid_thread_removed", "passive", passive_discount=discount) == (
        False,
        Decimal(1),
    )
    assert disposition("mid_thread_added", "passive", passive_discount=discount) == (
        True,
        Decimal(1),
    )
    assert disposition("auto_exited", "passive", passive_discount=discount) is None
    assert disposition("removed:wrong", "human", passive_discount=discount) is None
    assert identity_is_excluded(principal_id="owner", machine_id="m2g-sop-verification")
    assert identity_is_excluded(principal_id="fixture:gate", machine_id="owner-mac")
    assert not identity_is_excluded(principal_id="owner", machine_id="studio-mac")


def test_time_split_keeps_whole_gates_and_uses_newest_for_holdout() -> None:
    examples = tuple(
        _example(
            event=index,
            gate=gate,
            memory_id=POSITIVE_ID if index % 2 else NEGATIVE_ID,
            sem=float(index % 2),
            target=bool(index % 2),
            shown_as="injected",
        )
        for index, gate in enumerate((1, 1, 2, 2, 3, 3), start=1)
    )

    training, holdout, cutoff = split_gates(examples, holdout_fraction=0.34)

    assert {item.injection_id.int for item in training} == {1}
    assert {item.injection_id.int for item in holdout} == {2, 3}
    assert cutoff == BASE + timedelta(hours=1)


def test_whole_log_fit_is_deterministic_simplex_constrained_and_shrunk() -> None:
    examples = (
        _example(
            event=1,
            gate=1,
            memory_id=POSITIVE_ID,
            sem=1.0,
            target=True,
            shown_as="near_miss",
        ),
        _example(
            event=2,
            gate=1,
            memory_id=NEGATIVE_ID,
            sem=0.0,
            target=False,
            shown_as="injected",
        ),
    )
    settings = FitSettings(pair_margin=0.8, bias_l2=1.0)

    first = fit_pairwise(
        examples,
        incumbent_weights=(1 / 6,) * 6,
        settings=settings,
    )
    second = fit_pairwise(
        examples,
        incumbent_weights=(1 / 6,) * 6,
        settings=settings,
    )

    assert first == second
    assert sum(first.weights) == pytest.approx(1.0)
    assert all(weight >= 0.0 for weight in first.weights)
    assert first.weights[0] > 1 / 6
    assert first.bias_offsets[POSITIVE_ID] > 0.0
    assert first.bias_offsets[NEGATIVE_ID] < 0.0
    assert abs(first.bias_offsets[POSITIVE_ID]) < settings.pair_margin
    assert first.pair_count == 1


def test_binary_replay_counts_each_override_and_applies_passive_discount() -> None:
    examples = (
        _example(
            event=3,
            gate=2,
            memory_id=POSITIVE_ID,
            sem=1.0,
            target=True,
            shown_as="near_miss",
        ),
        _example(
            event=5,
            gate=2,
            memory_id=NEGATIVE_ID,
            sem=0.0,
            target=False,
            shown_as="injected",
            actor_weight=Decimal("0.25"),
        ),
    )

    incumbent = recorded_score(examples)
    challenger = challenger_score(
        examples,
        weights=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        bias_offsets={},
        tau=0.55,
    )

    assert incumbent.disagreements == 2
    assert incumbent.weighted_disagreements == Decimal("1.25")
    assert incumbent.injected_tokens == 5
    assert challenger.disagreements == 0
    assert challenger.weighted_disagreements == 0
    assert challenger.injected_tokens == 3


def test_replay_winner_requires_margin_except_for_exact_cheaper_tie() -> None:
    incumbent = ReplayScore(
        disagreements=4,
        weighted_disagreements=Decimal("4"),
        injected_tokens=100,
    )

    assert challenger_wins(
        incumbent,
        ReplayScore(
            disagreements=3,
            weighted_disagreements=Decimal("3"),
            injected_tokens=120,
        ),
        margin=Decimal("1"),
    )
    assert not challenger_wins(
        incumbent,
        ReplayScore(
            disagreements=3,
            weighted_disagreements=Decimal("3.25"),
            injected_tokens=80,
        ),
        margin=Decimal("1"),
    )
    assert challenger_wins(
        incumbent,
        ReplayScore(
            disagreements=4,
            weighted_disagreements=Decimal("4"),
            injected_tokens=99,
        ),
        margin=Decimal("1"),
    )
