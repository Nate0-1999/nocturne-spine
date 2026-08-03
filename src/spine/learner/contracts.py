"""Wire contracts for the authenticated M2F retrain trigger."""

from typing import Literal

from pydantic import BaseModel


class ReplayScoreView(BaseModel):
    disagreements: int
    weighted_disagreements: str
    injected_tokens: int


class RetrainResponse(BaseModel):
    status: Literal["insufficient_data", "not_better", "proposed"]
    incumbent_version: str
    proposal_version: str | None
    eligible_dispositions: int
    training_dispositions: int
    holdout_dispositions: int
    training_pairs: int
    incumbent: ReplayScoreView | None
    challenger: ReplayScoreView | None
    reason: str


__all__ = ["ReplayScoreView", "RetrainResponse"]
