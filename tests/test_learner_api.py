"""Live-Postgres contract tests for M2F proposal persistence and hygiene."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from spine.db.models import InjectionEvent
from spine.db.models import ScorerConfig as ScorerConfigRow
from spine.learner.service import LearnerService, LearnerSettings


def _service(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    min_dispositions: int = 4,
) -> LearnerService:
    return LearnerService(
        session_factory,
        settings=LearnerSettings(
            min_dispositions=min_dispositions,
            holdout_fraction=0.5,
            passive_discount=0.25,
            pair_margin=0.8,
            bias_l2=1.0,
            win_margin=1.0,
        ),
    )


async def _reset_proposals(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session, session.begin():
        await session.execute(delete(ScorerConfigRow).where(ScorerConfigRow.version != "v0"))


async def _insert_gate(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    gate: int,
    machine_id: str = "studio-mac",
) -> None:
    base = datetime(2026, 8, 3, tzinfo=UTC) + timedelta(hours=gate)
    injection_id = UUID(int=gate)
    rows = (
        InjectionEvent(
            event_uid=f"gate-{gate}-positive",
            injection_id=injection_id,
            thread_id=UUID(int=100 + gate),
            agent_id="general",
            machine_id=machine_id,
            principal_id="owner",
            project_key=None,
            agent_kind="general",
            prompt_text="learner fixture",
            scorer_version="v0",
            memory_id=UUID(int=1),
            memory_kind="fact",
            features={
                "sem": 1.0,
                "kw": 0.0,
                "time": 0.0,
                "proj": 0.0,
                "freq": 0.0,
                "hist": 0.0,
                "_memory": {"body": "positive evidence"},
            },
            score=0.42,
            rank=2,
            shown_as="near_miss",
            actor_class="human",
            outcome="added_back",
            ts=base,
        ),
        InjectionEvent(
            event_uid=f"gate-{gate}-negative",
            injection_id=injection_id,
            thread_id=UUID(int=100 + gate),
            agent_id="general",
            machine_id=machine_id,
            principal_id="owner",
            project_key=None,
            agent_kind="general",
            prompt_text="learner fixture",
            scorer_version="v0",
            memory_id=UUID(int=2),
            memory_kind="fact",
            features={
                "sem": 0.0,
                "kw": 0.0,
                "time": 0.0,
                "proj": 0.0,
                "freq": 0.0,
                "hist": 0.0,
                "_memory": {"body": "negative evidence"},
            },
            score=0.0,
            rank=1,
            shown_as="injected",
            actor_class="human",
            outcome="removed:not_relevant",
            ts=base,
        ),
    )
    async with session_factory() as session, session.begin():
        session.add_all(rows)


@pytest.mark.asyncio
async def test_retrain_proposes_inactive_content_addressed_winner_idempotently(
    memory_app,
    memory_client: AsyncClient,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A-031 is defended by verifying that retrain proposes inactive content addressed winner
    idempotently; this prevents drift in the learner proposal authority.
    """
    await _reset_proposals(memory_session_factory)
    memory_app.state.learner_service = _service(memory_session_factory)
    await _insert_gate(memory_session_factory, gate=1)
    await _insert_gate(memory_session_factory, gate=2)

    first = await memory_client.post("/retrain")
    second = await memory_client.post("/retrain")

    assert first.status_code == 200
    assert second.status_code == 200
    payload = first.json()
    assert payload["status"] == "proposed"
    assert payload["eligible_dispositions"] == 4
    assert payload["training_dispositions"] == 2
    assert payload["holdout_dispositions"] == 2
    assert payload["training_pairs"] == 1
    assert payload["incumbent"]["weighted_disagreements"] == "2"
    assert payload["challenger"]["weighted_disagreements"] == "0"
    assert second.json()["proposal_version"] == payload["proposal_version"]
    async with memory_session_factory() as session:
        proposals = (
            (await session.execute(select(ScorerConfigRow).where(ScorerConfigRow.version != "v0")))
            .scalars()
            .all()
        )
    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.active is False
    assert proposal.version == payload["proposal_version"]
    assert sum(proposal.weights.values()) == pytest.approx(1.0)
    assert proposal.params["tau"] == 0.55
    assert proposal.params["_learner"]["status"] == "proposed"
    assert proposal.params["_learner"]["bias_offsets"]
    await _reset_proposals(memory_session_factory)


@pytest.mark.asyncio
async def test_retrain_hygiene_excludes_whole_verification_gate(
    memory_app,
    memory_client: AsyncClient,
    memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A-031 is defended by verifying that retrain hygiene excludes whole verification gate;
    this prevents drift in the learner proposal authority.
    """
    await _reset_proposals(memory_session_factory)
    memory_app.state.learner_service = _service(memory_session_factory, min_dispositions=1)
    await _insert_gate(memory_session_factory, gate=3, machine_id="m2f-sop-verification")

    response = await memory_client.post("/retrain")

    assert response.status_code == 200
    assert response.json() == {
        "status": "insufficient_data",
        "incumbent_version": "v0",
        "proposal_version": None,
        "eligible_dispositions": 0,
        "training_dispositions": 0,
        "holdout_dispositions": 0,
        "training_pairs": 0,
        "incumbent": None,
        "challenger": None,
        "reason": "minimum disposition floor not reached: 0/1",
    }
