"""Add the append-only M2K scorer activation journal.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX scorer_config_one_active_idx ON scorer_config (active) WHERE active"
    )
    op.execute(
        """
        CREATE TABLE scorer_activation (
          event_uid        TEXT PRIMARY KEY,
          version          TEXT NOT NULL REFERENCES scorer_config(version),
          previous_version TEXT NOT NULL REFERENCES scorer_config(version),
          actor_class      TEXT NOT NULL CHECK (actor_class IN ('human','passive')),
          machine_id       TEXT NOT NULL CHECK (
            machine_id = btrim(machine_id) AND machine_id <> ''
          ),
          reason           TEXT NOT NULL CHECK (reason IN ('human_control','learner_proposal')),
          changes          JSONB NOT NULL,
          ts               TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX scorer_activation_ts_idx ON scorer_activation (ts, event_uid)")


def downgrade() -> None:
    op.execute("DROP TABLE scorer_activation")
    op.execute("DROP INDEX scorer_config_one_active_idx")
