"""Add the append-only A-051 learner retrain receipt journal.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE learner_run (
          run_uid                  TEXT PRIMARY KEY,
          trigger                  TEXT NOT NULL CHECK (trigger IN ('manual','background')),
          result                   TEXT NOT NULL CHECK (
            result IN ('insufficient_data','not_better','proposed')
          ),
          incumbent_version        TEXT NOT NULL REFERENCES scorer_config(version),
          proposal_version         TEXT REFERENCES scorer_config(version),
          eligible_dispositions    BIGINT NOT NULL CHECK (eligible_dispositions >= 0),
          training_dispositions    BIGINT NOT NULL CHECK (training_dispositions >= 0),
          holdout_dispositions     BIGINT NOT NULL CHECK (holdout_dispositions >= 0),
          training_pairs           BIGINT NOT NULL CHECK (training_pairs >= 0),
          source_boundary          TEXT,
          incumbent                JSONB,
          challenger               JSONB,
          reason                   TEXT NOT NULL,
          ts                       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX learner_run_ts_idx ON learner_run (ts, run_uid)")
    op.execute(
        """
        CREATE FUNCTION learner_run_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'learner_run is append-only';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER learner_run_append_only
        BEFORE UPDATE OR DELETE ON learner_run
        FOR EACH ROW EXECUTE FUNCTION learner_run_reject_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER learner_run_append_only ON learner_run")
    op.execute("DROP FUNCTION learner_run_reject_mutation()")
    op.execute("DROP TABLE learner_run")
