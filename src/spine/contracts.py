"""Shared strict base for the exact SPEC C.4 request bodies."""

from pydantic import BaseModel, ConfigDict


class ContractRequest(BaseModel):
    """Reject fields outside the literal cross-repository request contract."""

    model_config = ConfigDict(extra="forbid")
