"""Activate the first share-aware scorer without rewriting prior versions.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-24
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from spine.ids import mint_ulid

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    source = (
        connection.execute(text("SELECT version, weights, params FROM scorer_config WHERE active"))
        .mappings()
        .one()
    )
    params = dict(source["params"])
    params.pop("budget_tokens", None)
    params.pop("budget_pct", None)
    params["memory_context_share"] = 0.10
    params["_m3ms_activation"] = {
        "migration": "0017",
        "amendment": "A-061",
        "previous_version": source["version"],
    }
    target_version = "m3ms-share-v1"
    connection.execute(text("UPDATE scorer_config SET active = false WHERE active"))
    connection.execute(
        text(
            """
            INSERT INTO scorer_config (version, weights, params, active)
            VALUES (:version, CAST(:weights AS jsonb), CAST(:params AS jsonb), true)
            """
        ),
        {
            "version": target_version,
            "weights": json.dumps(source["weights"], sort_keys=True),
            "params": json.dumps(params, sort_keys=True),
        },
    )
    changes = {
        "scorer.memory_context_share": {"before": None, "after": 0.10},
        "scorer.budget_tokens": {"before": source["params"].get("budget_tokens"), "after": None},
        "scorer.budget_pct": {"before": source["params"].get("budget_pct"), "after": None},
        "_contract": {"packet": "M3MS", "amendment": "A-061"},
    }
    connection.execute(
        text(
            """
            INSERT INTO scorer_activation (
              event_uid, version, previous_version, actor_class, machine_id,
              reason, changes
            ) VALUES (
              :event_uid, :version, :previous_version, 'passive',
              'spine:migration:0017', 'contract_migration', CAST(:changes AS jsonb)
            )
            """
        ),
        {
            "event_uid": mint_ulid(),
            "version": target_version,
            "previous_version": source["version"],
            "changes": json.dumps(changes, sort_keys=True),
        },
    )


def downgrade() -> None:
    connection = op.get_bind()
    target = (
        connection.execute(
            text(
                """
                SELECT params -> '_m3ms_activation' ->> 'previous_version' AS previous_version
                FROM scorer_config
                WHERE version = 'm3ms-share-v1'
                """
            )
        )
        .mappings()
        .one_or_none()
    )
    previous_version = target["previous_version"] if target is not None else None
    if previous_version is None:
        previous_version = connection.scalar(
            text(
                "SELECT previous_version FROM scorer_activation "
                "WHERE machine_id = 'spine:migration:0017' ORDER BY ts DESC LIMIT 1"
            )
        )
    if previous_version is not None:
        connection.execute(text("UPDATE scorer_config SET active = false WHERE active"))
        connection.execute(
            text("UPDATE scorer_config SET active = true WHERE version = :version"),
            {"version": previous_version},
        )
    connection.execute(
        text(
            "DELETE FROM scorer_activation "
            "WHERE reason = 'contract_migration' AND machine_id = 'spine:migration:0017'"
        )
    )
    connection.execute(text("DELETE FROM scorer_config WHERE version = 'm3ms-share-v1'"))
