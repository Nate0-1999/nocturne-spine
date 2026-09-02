"""Stamp memory birthplace folders and activate folder proximity.

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-02
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from spine.ids import mint_ulid

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_unit ADD COLUMN origin_location TEXT")
    connection = op.get_bind()
    source = (
        connection.execute(text("SELECT version, weights, params FROM scorer_config WHERE active"))
        .mappings()
        .one()
    )
    params = dict(source["params"])
    params["where_weight"] = 0.04
    params["_m3tl_activation"] = {
        "migration": "0021",
        "amendment": "A-063",
        "previous_version": source["version"],
    }
    target_version = "m3tl-where-v1"
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
    connection.execute(
        text(
            """
            INSERT INTO scorer_activation (
              event_uid, version, previous_version, actor_class, machine_id,
              reason, changes
            ) VALUES (
              :event_uid, :version, :previous_version, 'passive',
              'spine:migration:0021', 'contract_migration', CAST(:changes AS jsonb)
            )
            """
        ),
        {
            "event_uid": mint_ulid(),
            "version": target_version,
            "previous_version": source["version"],
            "changes": json.dumps(
                {
                    "scorer.where_weight": {"before": None, "after": 0.04},
                    "_contract": {"packet": "M3TL", "amendment": "A-063"},
                },
                sort_keys=True,
            ),
        },
    )


def downgrade() -> None:
    connection = op.get_bind()
    target = (
        connection.execute(
            text(
                """
                SELECT params -> '_m3tl_activation' ->> 'previous_version' AS previous_version
                FROM scorer_config WHERE version = 'm3tl-where-v1'
                """
            )
        )
        .mappings()
        .one_or_none()
    )
    previous_version = target["previous_version"] if target is not None else None
    if previous_version is not None:
        connection.execute(text("UPDATE scorer_config SET active = false WHERE active"))
        connection.execute(
            text("UPDATE scorer_config SET active = true WHERE version = :version"),
            {"version": previous_version},
        )
    connection.execute(
        text(
            "DELETE FROM scorer_activation "
            "WHERE reason = 'contract_migration' AND machine_id = 'spine:migration:0021'"
        )
    )
    connection.execute(text("DELETE FROM scorer_config WHERE version = 'm3tl-where-v1'"))
    op.execute("ALTER TABLE memory_unit DROP COLUMN origin_location")
