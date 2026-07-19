"""Pure, deterministic implementation of SPEC C.3 scorer v0."""

from __future__ import annotations

import math
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Any
from uuid import UUID

from spine.tokens import cl100k_token_count

_SECONDS_PER_DAY = 86_400
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "he",
        "in",
        "is",
        "it",
        "its",
        "of",
        "on",
        "that",
        "the",
        "to",
        "was",
        "were",
        "will",
        "with",
    }
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ScorerWeights:
    """The six linear feature weights for one immutable scorer version."""

    sem: float
    kw: float
    time: float
    proj: float
    freq: float
    hist: float


@dataclass(frozen=True, slots=True, kw_only=True)
class ScorerParams:
    """Selection and decay parameters for one immutable scorer version."""

    tau: float
    top_k: int
    near_miss_k: int
    budget_tokens: int
    budget_pct: float
    half_life_time_days: float
    half_life_hist_days: float
    candidate_pool: int

    def __post_init__(self) -> None:
        if not 0.0 <= self.tau <= 1.0:
            raise ValueError("tau must be between zero and one")
        if not 0 < self.top_k <= 8:
            raise ValueError("top_k must be between one and eight")
        if self.near_miss_k < 0:
            raise ValueError("near_miss_k must not be negative")
        if self.budget_tokens <= 0:
            raise ValueError("budget_tokens must be positive")
        if not 0.0 < self.budget_pct <= 1.0:
            raise ValueError("budget_pct must be greater than zero and at most one")
        if self.half_life_time_days <= 0.0 or self.half_life_hist_days <= 0.0:
            raise ValueError("scorer half lives must be positive")
        if self.candidate_pool <= 0:
            raise ValueError("candidate_pool must be positive")


@dataclass(frozen=True, slots=True, kw_only=True)
class ScorerConfig:
    """Versioned scorer configuration loaded from ``scorer_config``."""

    version: str
    weights: ScorerWeights
    params: ScorerParams

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("scorer version must not be blank")
        values = (
            self.weights.sem,
            self.weights.kw,
            self.weights.time,
            self.weights.proj,
            self.weights.freq,
            self.weights.hist,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("scorer weights must be finite")

    @classmethod
    def from_mappings(
        cls,
        *,
        version: str,
        weights: Mapping[str, Any],
        params: Mapping[str, Any],
    ) -> ScorerConfig:
        """Build the typed pure boundary from the two JSONB config objects."""

        return cls(
            version=version,
            weights=ScorerWeights(
                sem=_number(weights, "sem"),
                kw=_number(weights, "kw"),
                time=_number(weights, "time"),
                proj=_number(weights, "proj"),
                freq=_number(weights, "freq"),
                hist=_number(weights, "hist"),
            ),
            params=ScorerParams(
                tau=_number(params, "tau"),
                top_k=_integer(params, "top_k"),
                near_miss_k=_integer(params, "near_miss_k"),
                budget_tokens=_integer(params, "budget_tokens"),
                budget_pct=_number(params, "budget_pct"),
                half_life_time_days=_number(params, "half_life_time_days"),
                half_life_hist_days=_number(params, "half_life_hist_days"),
                candidate_pool=_integer(params, "candidate_pool"),
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoringCandidate:
    """Detached memory head and revision facts needed by scoring and its caller."""

    memory_id: UUID
    label: str
    body: str
    kind: str
    keywords: tuple[str, ...]
    embedding: tuple[float, ...]
    project_key: str | None
    pin: bool
    updated_at: datetime
    last_human_edit_at: datetime | None
    stats: Mapping[str, Any]
    bias: float
    revision: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreFeatures:
    """The exact six explainability features persisted for every decision."""

    sem: float
    kw: float
    time: float
    proj: float
    freq: float
    hist: float

    def as_dict(self) -> dict[str, float]:
        """Return the exact public feature object without scorer internals."""

        return {
            "sem": self.sem,
            "kw": self.kw,
            "time": self.time,
            "proj": self.proj,
            "freq": self.freq,
            "hist": self.hist,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoredCandidate:
    """One candidate with its complete-order rank and body token cost."""

    candidate: ScoringCandidate
    features: ScoreFeatures
    score: float
    rank: int
    token_cost: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoringSelection:
    """Cards returned by prepare plus deterministic budget accounting."""

    injected: tuple[ScoredCandidate, ...]
    near_misses: tuple[ScoredCandidate, ...]
    regular_budget: int
    pin_token_cost: int


def score_and_select(
    *,
    prompt: str,
    query_embedding: Sequence[float],
    snapshot_ts: datetime,
    thread_project_key: str | None,
    pinned_candidates: Sequence[ScoringCandidate],
    regular_candidates: Sequence[ScoringCandidate],
    model_context_tokens: int,
    config: ScorerConfig,
) -> ScoringSelection:
    """Score an eligible pool and apply scorer-v0 pin, rank, and budget law."""

    if model_context_tokens <= 0:
        raise ValueError("model_context_tokens must be positive")

    query = _validated_vector(query_embedding, name="query embedding")
    pins = tuple(pinned_candidates)
    regular = tuple(regular_candidates)
    _validate_candidate_partition(pins, regular)

    prompt_keywords = _keywords(prompt)
    pin_scores = [
        _score_candidate(
            candidate,
            query=query,
            prompt_keywords=prompt_keywords,
            snapshot_ts=snapshot_ts,
            thread_project_key=thread_project_key,
            weights=config.weights,
            params=config.params,
        )
        for candidate in pins
    ]
    pin_scores.sort(key=lambda scored: scored.candidate.memory_id.int)

    # The vector pool boundary precedes linear scoring. Reapplying the exact
    # order here makes the pure layer deterministic even if a caller supplies
    # a larger unsorted eligible set.
    semantic_pool = [(_vector_similarity(candidate, query), candidate) for candidate in regular]
    semantic_pool.sort(key=lambda item: (-item[0], item[1].memory_id.int))
    semantic_pool = semantic_pool[: config.params.candidate_pool]
    vector_pool = [
        _score_candidate(
            candidate,
            query=query,
            semantic=max(0.0, semantic),
            prompt_keywords=prompt_keywords,
            snapshot_ts=snapshot_ts,
            thread_project_key=thread_project_key,
            weights=config.weights,
            params=config.params,
        )
        for semantic, candidate in semantic_pool
    ]
    vector_pool.sort(key=lambda scored: (-scored.score, scored.candidate.memory_id.int))

    ranked_pins = tuple(
        _with_rank(scored, rank=index) for index, scored in enumerate(pin_scores, start=1)
    )
    ranked_regular = tuple(
        _with_rank(scored, rank=index)
        for index, scored in enumerate(vector_pool, start=len(ranked_pins) + 1)
    )

    pin_token_cost = sum(scored.token_cost for scored in ranked_pins)
    budget_pct = Fraction(str(config.params.budget_pct))
    percentage_budget = budget_pct.numerator * model_context_tokens // budget_pct.denominator
    base_budget = min(config.params.budget_tokens, percentage_budget)
    regular_budget = max(0, base_budget - pin_token_cost)
    remaining_budget = regular_budget
    selected_regular: list[ScoredCandidate] = []
    unselected_regular: list[ScoredCandidate] = []

    for scored in ranked_regular:
        selectable = (
            len(selected_regular) < config.params.top_k
            and scored.score >= config.params.tau
            and scored.token_cost <= remaining_budget
        )
        if selectable:
            selected_regular.append(scored)
            remaining_budget -= scored.token_cost
        else:
            unselected_regular.append(scored)

    return ScoringSelection(
        injected=(*ranked_pins, *selected_regular),
        near_misses=tuple(unselected_regular[: config.params.near_miss_k]),
        regular_budget=regular_budget,
        pin_token_cost=pin_token_cost,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class _UnrankedCandidate:
    candidate: ScoringCandidate
    features: ScoreFeatures
    score: float
    token_cost: int


def _score_candidate(
    candidate: ScoringCandidate,
    *,
    query: tuple[float, ...],
    semantic: float | None = None,
    prompt_keywords: frozenset[str],
    snapshot_ts: datetime,
    thread_project_key: str | None,
    weights: ScorerWeights,
    params: ScorerParams,
) -> _UnrankedCandidate:
    memory_keywords = set(_tokens(candidate.label))
    for keyword in candidate.keywords:
        memory_keywords.update(_tokens(keyword))
    keyword_overlap = len(prompt_keywords.intersection(memory_keywords)) / max(
        1, len(prompt_keywords)
    )

    features = ScoreFeatures(
        sem=(_semantic_similarity(candidate, query) if semantic is None else semantic),
        kw=min(1.0, keyword_overlap),
        time=_decay(
            snapshot_ts=snapshot_ts,
            event_ts=candidate.updated_at,
            half_life_days=params.half_life_time_days,
        ),
        proj=_project_feature(
            thread_project_key=thread_project_key,
            memory_project_key=candidate.project_key,
        ),
        freq=min(1.0, _citations(candidate.stats) / 10.0),
        hist=(
            0.0
            if candidate.last_human_edit_at is None
            else _decay(
                snapshot_ts=snapshot_ts,
                event_ts=candidate.last_human_edit_at,
                half_life_days=params.half_life_hist_days,
            )
        ),
    )
    score = math.fsum(
        (
            weights.sem * features.sem,
            weights.kw * features.kw,
            weights.time * features.time,
            weights.proj * features.proj,
            weights.freq * features.freq,
            weights.hist * features.hist,
            candidate.bias,
        )
    )
    if not math.isfinite(score):
        raise ValueError(f"score for {candidate.memory_id} is not finite")
    return _UnrankedCandidate(
        candidate=candidate,
        features=features,
        score=_postgres_real(score),
        token_cost=cl100k_token_count(candidate.body),
    )


def _with_rank(scored: _UnrankedCandidate, *, rank: int) -> ScoredCandidate:
    return ScoredCandidate(
        candidate=scored.candidate,
        features=scored.features,
        score=scored.score,
        rank=rank,
        token_cost=scored.token_cost,
    )


def _validate_candidate_partition(
    pins: Sequence[ScoringCandidate], regular: Sequence[ScoringCandidate]
) -> None:
    if any(not candidate.pin for candidate in pins):
        raise ValueError("every pinned candidate must have pin=true")
    if any(candidate.pin for candidate in regular):
        raise ValueError("regular candidates must have pin=false")
    ids = [candidate.memory_id for candidate in (*pins, *regular)]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate memory IDs must be unique")


def _tokens(value: str) -> tuple[str, ...]:
    lowered = value.lower()
    tokens: list[str] = []
    current: list[str] = []
    for character in lowered:
        if character.isalnum():
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


def _keywords(value: str) -> frozenset[str]:
    return frozenset(token for token in _tokens(value) if token not in _STOPWORDS)


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    numerator = math.fsum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(math.fsum(value * value for value in left))
    right_norm = math.sqrt(math.fsum(value * value for value in right))
    cosine = numerator / (left_norm * right_norm)
    return min(1.0, max(-1.0, cosine))


def _vector_similarity(candidate: ScoringCandidate, query: tuple[float, ...]) -> float:
    embedding = _validated_vector(candidate.embedding, name=f"embedding for {candidate.memory_id}")
    if len(query) != len(embedding):
        raise ValueError(
            f"embedding for {candidate.memory_id} has {len(embedding)} dimensions; "
            f"query has {len(query)}"
        )
    return _cosine(query, embedding)


def _semantic_similarity(candidate: ScoringCandidate, query: tuple[float, ...]) -> float:
    return max(0.0, _vector_similarity(candidate, query))


def _decay(*, snapshot_ts: datetime, event_ts: datetime, half_life_days: float) -> float:
    age_days = max(0.0, (snapshot_ts - event_ts).total_seconds() / _SECONDS_PER_DAY)
    return 2.0 ** (-age_days / half_life_days)


def _project_feature(*, thread_project_key: str | None, memory_project_key: str | None) -> float:
    if thread_project_key is not None and memory_project_key == thread_project_key:
        return 1.0
    if memory_project_key is None:
        return 0.5
    return 0.0


def _citations(stats: Mapping[str, Any]) -> float:
    value = stats.get("citations", 0)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("stats.citations must be numeric")
    normalized = float(value)
    if normalized < 0.0 or not math.isfinite(normalized):
        raise ValueError("stats.citations must be a finite non-negative number")
    return normalized


def _validated_vector(values: Sequence[float], *, name: str) -> tuple[float, ...]:
    vector: list[float] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must contain only numbers")
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{name} must contain only finite numbers")
        vector.append(normalized)
    if not vector:
        raise ValueError(f"{name} must not be empty")
    if math.fsum(value * value for value in vector) == 0.0:
        raise ValueError(f"{name} must not have zero norm")
    return tuple(vector)


def _postgres_real(value: float) -> float:
    """Quantize score decisions once to C.2's IEEE-754 REAL width."""

    return struct.unpack("!f", struct.pack("!f", value))[0]


def _number(mapping: Mapping[str, Any], key: str) -> float:
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"scorer config {key} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"scorer config {key} must be finite")
    return normalized


def _integer(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"scorer config {key} must be an integer")
    return value


__all__ = [
    "ScoreFeatures",
    "ScoredCandidate",
    "ScorerConfig",
    "ScorerParams",
    "ScorerWeights",
    "ScoringCandidate",
    "ScoringSelection",
    "score_and_select",
]
