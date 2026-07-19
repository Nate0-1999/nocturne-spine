"""Hand-computed golden cases for the pure SPEC C.3 scorer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from spine.inject.scorer import (
    ScorerConfig,
    ScorerParams,
    ScorerWeights,
    ScoringCandidate,
    score_and_select,
)

SNAPSHOT = datetime(2026, 7, 19, 12, tzinfo=UTC)
WEIGHTS = ScorerWeights(sem=0.42, kw=0.16, time=0.11, proj=0.16, freq=0.08, hist=0.07)


def _config(**changes: Any) -> ScorerConfig:
    values: dict[str, Any] = {
        "tau": 0.55,
        "top_k": 8,
        "near_miss_k": 3,
        "budget_tokens": 3000,
        "budget_pct": 0.05,
        "half_life_time_days": 14,
        "half_life_hist_days": 7,
        "candidate_pool": 50,
    }
    values.update(changes)
    return ScorerConfig(version="v0", weights=WEIGHTS, params=ScorerParams(**values))


def _candidate(
    number: int,
    *,
    label: str = "memory",
    body: str = "tiny",
    kind: str = "fact",
    keywords: tuple[str, ...] = (),
    embedding: tuple[float, ...] = (1.0, 0.0),
    project_key: str | None = None,
    pin: bool = False,
    updated_at: datetime = SNAPSHOT,
    last_human_edit_at: datetime | None = None,
    citations: int = 0,
    bias: float = 0.0,
) -> ScoringCandidate:
    return ScoringCandidate(
        memory_id=UUID(int=number),
        label=label,
        body=body,
        kind=kind,
        keywords=keywords,
        embedding=embedding,
        project_key=project_key,
        pin=pin,
        updated_at=updated_at,
        last_human_edit_at=last_human_edit_at,
        stats={"citations": citations},
        bias=bias,
        revision=number,
    )


def test_golden_six_feature_score_uses_enacted_tokenizer_and_snapshot_clock() -> None:
    # Hand calculation:
    # sem=.6; kw=3/3=1; time=2^(-14/14)=.5; proj=1;
    # freq=5/10=.5; hist=2^(-7/7)=.5.
    # score=.42*.6 + .16 + .11*.5 + .16 + .08*.5 + .07*.5 + .03 = .732.
    candidate = _candidate(
        1,
        label="Café roadmap",
        body="one two",
        keywords=("NAÏVE2", "road-and-more"),
        embedding=(0.6, 0.8),
        project_key="atlas",
        updated_at=SNAPSHOT - timedelta(days=14),
        last_human_edit_at=SNAPSHOT - timedelta(days=7),
        citations=5,
        bias=0.03,
    )

    result = score_and_select(
        prompt="The CAFÉ_and naïve2 from ROAD",
        query_embedding=(1.0, 0.0),
        snapshot_ts=SNAPSHOT,
        thread_project_key="atlas",
        pinned_candidates=(),
        regular_candidates=(candidate,),
        model_context_tokens=10_000,
        config=_config(),
    )

    assert len(result.injected) == 1
    scored = result.injected[0]
    assert scored.features.as_dict() == pytest.approx(
        {"sem": 0.6, "kw": 1.0, "time": 0.5, "proj": 1.0, "freq": 0.5, "hist": 0.5}
    )
    assert scored.score == pytest.approx(0.732)
    assert scored.rank == 1
    assert scored.token_cost == 2


def test_golden_tau_is_inclusive_and_negative_cosine_clamps_to_zero() -> None:
    # Shared subtotal: sem=1 -> .42, time=1 -> .11, global project=.5 ->
    # .08, for .61. Bias -.06 lands exactly on tau; -.061 lands at .549.
    at_tau = _candidate(
        1,
        embedding=(1.0, 0.0),
        project_key=None,
        bias=-0.06,
    )
    below_tau = _candidate(
        2,
        embedding=(1.0, 0.0),
        project_key=None,
        bias=-0.061,
    )
    negative = _candidate(
        3,
        embedding=(-1.0, 0.0),
        project_key=None,
    )

    result = score_and_select(
        prompt="the and",
        query_embedding=(1.0, 0.0),
        snapshot_ts=SNAPSHOT,
        thread_project_key="atlas",
        pinned_candidates=(),
        regular_candidates=(negative, below_tau, at_tau),
        model_context_tokens=10_000,
        config=_config(),
    )

    assert [item.candidate.memory_id.int for item in result.injected] == [1]
    assert result.injected[0].score == pytest.approx(0.55)
    assert [item.candidate.memory_id.int for item in result.near_misses] == [2, 3]
    assert [item.score for item in result.near_misses] == pytest.approx([0.549, 0.19])
    assert result.near_misses[1].features.sem == 0.0


def test_golden_selection_preserves_pin_score_order_ranks_and_greedy_skips() -> None:
    # With only stopwords in the prompt, every regular has the same .61 base:
    # .42*1 sem + .11*1 time + .16*.5 global project = .61.
    # Biases therefore make regular scores .90, .80, .70, .60, .50.
    pins = (
        _candidate(2, pin=True, body="one two"),
        _candidate(1, pin=True, body="pin"),
    )
    regular = (
        _candidate(14, bias=-0.11),
        _candidate(13, bias=-0.01),
        _candidate(12, body="one two", bias=0.09),
        _candidate(11, body="one two three", kind="pinned", bias=0.19),
        _candidate(10, body="one two three", bias=0.29),
    )

    result = score_and_select(
        prompt="the and from",
        query_embedding=(1.0, 0.0),
        snapshot_ts=SNAPSHOT,
        thread_project_key="atlas",
        pinned_candidates=pins,
        regular_candidates=regular,
        model_context_tokens=160,
        config=_config(top_k=2, budget_tokens=8, candidate_pool=5),
    )

    # floor(.05*160)=8, then 3 pin tokens leave a five-token regular budget.
    # Rank 3 costs three and is accepted; rank 4 costs three and is skipped;
    # rank 5 costs two and is accepted. Ranks 6 and 7 fail top-k and threshold.
    assert result.pin_token_cost == 3
    assert result.regular_budget == 5
    assert [item.candidate.memory_id.int for item in result.injected] == [1, 2, 10, 12]
    assert [item.rank for item in result.injected] == [1, 2, 3, 5]
    assert [item.candidate.memory_id.int for item in result.near_misses] == [11, 13, 14]
    assert [item.rank for item in result.near_misses] == [4, 6, 7]
    assert [item.score for item in result.injected[2:]] == pytest.approx([0.90, 0.70])
    assert [item.score for item in result.near_misses] == pytest.approx([0.80, 0.60, 0.50])


def test_golden_pins_can_exceed_budget_and_bypass_a_below_tau_score() -> None:
    # The pin has sem=0 (negative cosine clamps), kw=0, time=1 (future age
    # clamps), proj=.5, freq=1, hist=1. Its score is .11+.08+.08+.07=.34.
    pin = _candidate(
        1,
        body="one two three",
        embedding=(-1.0, 0.0),
        pin=True,
        updated_at=SNAPSHOT + timedelta(days=1),
        last_human_edit_at=SNAPSHOT + timedelta(days=1),
        citations=99,
    )
    regular = _candidate(2, body="tiny")

    result = score_and_select(
        prompt="the",
        query_embedding=(1.0, 0.0),
        snapshot_ts=SNAPSHOT,
        thread_project_key=None,
        pinned_candidates=(pin,),
        regular_candidates=(regular,),
        model_context_tokens=40,
        config=_config(budget_tokens=2),
    )

    assert result.pin_token_cost == 3
    assert result.regular_budget == 0
    assert [item.candidate.memory_id.int for item in result.injected] == [1]
    assert result.injected[0].score == pytest.approx(0.34)
    assert result.injected[0].features.as_dict() == pytest.approx(
        {"sem": 0.0, "kw": 0.0, "time": 1.0, "proj": 0.5, "freq": 1.0, "hist": 1.0}
    )
    assert [item.candidate.memory_id.int for item in result.near_misses] == [2]
    assert result.near_misses[0].rank == 2


def test_vector_pool_precedes_score_and_breaks_cosine_ties_by_memory_id() -> None:
    candidates = (
        _candidate(30, embedding=(0.8, 0.6), bias=100.0),
        _candidate(20, embedding=(1.0, 0.0)),
        _candidate(10, embedding=(0.8, 0.6)),
    )

    result = score_and_select(
        prompt="the",
        query_embedding=(1.0, 0.0),
        snapshot_ts=SNAPSHOT,
        thread_project_key=None,
        pinned_candidates=(),
        regular_candidates=candidates,
        model_context_tokens=10_000,
        config=_config(tau=0.0, candidate_pool=2),
    )

    # Candidate 30 would dominate the linear sort via bias, but candidate 10
    # wins their .8-cosine tie at the vector-pool boundary.
    assert [item.candidate.memory_id.int for item in result.injected] == [20, 10]
    assert [item.rank for item in result.injected] == [1, 2]
    returned = (*result.injected, *result.near_misses)
    assert all(item.candidate.memory_id.int != 30 for item in returned)


def test_vector_pool_orders_raw_negative_cosines_before_feature_clamping() -> None:
    strongly_negative = _candidate(1, embedding=(-1.0, 0.0))
    less_negative = _candidate(2, embedding=(-0.5, 3**0.5 / 2))

    result = score_and_select(
        prompt="the",
        query_embedding=(1.0, 0.0),
        snapshot_ts=SNAPSHOT,
        thread_project_key=None,
        pinned_candidates=(),
        regular_candidates=(strongly_negative, less_negative),
        model_context_tokens=10_000,
        config=_config(tau=0.0, candidate_pool=1),
    )

    assert [item.candidate.memory_id.int for item in result.injected] == [2]
    assert result.injected[0].features.sem == 0.0


def test_postgres_real_quantization_precedes_score_tie_breaking() -> None:
    lower_id = _candidate(1, bias=0.0)
    higher_raw_score = _candidate(2, bias=1e-9)

    result = score_and_select(
        prompt="the",
        query_embedding=(1.0, 0.0),
        snapshot_ts=SNAPSHOT,
        thread_project_key=None,
        pinned_candidates=(),
        regular_candidates=(higher_raw_score, lower_id),
        model_context_tokens=10_000,
        config=_config(tau=0.0),
    )

    assert result.injected[0].score == result.injected[1].score
    assert [item.candidate.memory_id.int for item in result.injected] == [1, 2]


def test_percentage_budget_saturates_for_an_arbitrarily_large_context_integer() -> None:
    candidate = _candidate(1)

    result = score_and_select(
        prompt="the",
        query_embedding=(1.0, 0.0),
        snapshot_ts=SNAPSHOT,
        thread_project_key=None,
        pinned_candidates=(),
        regular_candidates=(candidate,),
        model_context_tokens=10**400,
        config=_config(),
    )

    assert result.regular_budget == 3000
    assert [item.candidate.memory_id.int for item in result.injected] == [1]


def test_config_json_boundary_uses_only_the_scoring_fields() -> None:
    config = ScorerConfig.from_mappings(
        version="v0",
        weights={"sem": 0.42, "kw": 0.16, "time": 0.11, "proj": 0.16, "freq": 0.08, "hist": 0.07},
        params={
            "tau": 0.55,
            "top_k": 8,
            "near_miss_k": 3,
            "budget_tokens": 3000,
            "budget_pct": 0.05,
            "half_life_time_days": 14,
            "half_life_hist_days": 7,
            "candidate_pool": 50,
            "never_bias_step": -0.15,
            "quarantine_kills": 3,
        },
    )

    assert config == _config()
