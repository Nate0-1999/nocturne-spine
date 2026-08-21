"""Add conversation birthplace and activate the first thread-aware scorer.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-21
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from spine.ids import mint_ulid

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_unit ADD COLUMN origin_thread_id UUID")
    op.create_index(
        "memory_unit_principal_origin_thread_idx",
        "memory_unit",
        ["principal_id", "origin_thread_id"],
        postgresql_where=text("origin_thread_id IS NOT NULL"),
    )

    connection = op.get_bind()
    source = (
        connection.execute(text("SELECT version, weights, params FROM scorer_config WHERE active"))
        .mappings()
        .one()
    )
    params = dict(source["params"])
    params["thread_weight"] = 0.08
    params["_m3ti_activation"] = {
        "migration": "0016",
        "amendment": "A-060",
        "previous_version": source["version"],
    }
    target_version = "m3ti-thread-v1"
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
        "scorer.thread_weight": {"before": None, "after": 0.08},
        "_contract": {"packet": "M3TI", "amendment": "A-060"},
    }
    connection.execute(
        text(
            """
            INSERT INTO scorer_activation (
              event_uid, version, previous_version, actor_class, machine_id,
              reason, changes
            ) VALUES (
              :event_uid, :version, :previous_version, 'passive',
              'spine:migration:0016', 'contract_migration', CAST(:changes AS jsonb)
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
                SELECT version, params -> '_m3ti_activation' ->> 'previous_version'
                       AS previous_version
                FROM scorer_config
                WHERE version = 'm3ti-thread-v1'
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
                "WHERE machine_id = 'spine:migration:0016' ORDER BY ts DESC LIMIT 1"
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
            "WHERE reason = 'contract_migration' AND machine_id = 'spine:migration:0016'"
        )
    )
    connection.execute(text("DELETE FROM scorer_config WHERE version = 'm3ti-thread-v1'"))
    op.drop_index("memory_unit_principal_origin_thread_idx", table_name="memory_unit")
    op.execute("ALTER TABLE memory_unit DROP COLUMN origin_thread_id")
