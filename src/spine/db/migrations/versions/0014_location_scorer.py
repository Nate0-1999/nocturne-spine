"""Activate the R16 location-aware scorer without rewriting prior versions.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-17
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from spine.ids import mint_ulid

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("scorer_activation_reason_check", "scorer_activation", type_="check")
    op.create_check_constraint(
        "scorer_activation_reason_check",
        "scorer_activation",
        "reason IN ('human_control','learner_proposal','contract_migration')",
    )
    connection = op.get_bind()
    source = (
        connection.execute(text("SELECT version, weights, params FROM scorer_config WHERE active"))
        .mappings()
        .one()
    )
    params = dict(source["params"])
    params.update({"location_weight": 0.08, "half_life_location_hops": 2.0})
    params["_m3f_activation"] = {
        "migration": "0014",
        "requirement": "R16",
        "previous_version": source["version"],
    }
    target_version = "m3f-location-v1"
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
        "scorer.location_weight": {"before": None, "after": 0.08},
        "scorer.half_life_location_hops": {"before": None, "after": 2.0},
        "_contract": {"requirement": "R16", "amendment": "A-058"},
    }
    connection.execute(
        text(
            """
            INSERT INTO scorer_activation (
              event_uid, version, previous_version, actor_class, machine_id,
              reason, changes
            ) VALUES (
              :event_uid, :version, :previous_version, 'passive',
              'spine:migration:0014', 'contract_migration', CAST(:changes AS jsonb)
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
            SELECT version, params -> '_m3f_activation' ->> 'previous_version'
                   AS previous_version
            FROM scorer_config
            WHERE version = 'm3f-location-v1'
            """
            )
        )
        .mappings()
        .one()
    )
    connection.execute(text("UPDATE scorer_config SET active = false WHERE active"))
    connection.execute(
        text("UPDATE scorer_config SET active = true WHERE version = :version"),
        {"version": target["previous_version"]},
    )
    connection.execute(
        text(
            "DELETE FROM scorer_activation "
            "WHERE reason = 'contract_migration' AND machine_id = 'spine:migration:0014'"
        )
    )
    connection.execute(
        text("DELETE FROM scorer_config WHERE version = :version"),
        {"version": target["version"]},
    )
    op.drop_constraint("scorer_activation_reason_check", "scorer_activation", type_="check")
    op.create_check_constraint(
        "scorer_activation_reason_check",
        "scorer_activation",
        "reason IN ('human_control','learner_proposal')",
    )
