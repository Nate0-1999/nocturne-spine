"""Add the append-only cross-loop optimization ledger.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-31
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE optimization_run (
          run_uid TEXT PRIMARY KEY,
          loop TEXT NOT NULL CHECK (loop = btrim(loop) AND loop <> ''),
          trigger_kind TEXT NOT NULL
            CHECK (trigger_kind = btrim(trigger_kind) AND trigger_kind <> ''),
          trigger_event_uid TEXT NOT NULL
            CHECK (trigger_event_uid = btrim(trigger_event_uid) AND trigger_event_uid <> ''),
          trigger_thread_id UUID,
          corpus_fingerprint TEXT NOT NULL
            CHECK (corpus_fingerprint ~ '^[0-9a-f]{64}$'),
          corpus_size BIGINT NOT NULL CHECK (corpus_size >= 0),
          corpus_max_size BIGINT NOT NULL CHECK (corpus_max_size > 0),
          corpus_stratification JSONB NOT NULL
            CHECK (jsonb_typeof(corpus_stratification) = 'object'),
          incumbent_version TEXT NOT NULL REFERENCES scorer_config(version),
          challenger_version TEXT REFERENCES scorer_config(version),
          incumbent_params JSONB NOT NULL CHECK (jsonb_typeof(incumbent_params) = 'object'),
          challenger_params JSONB
            CHECK (challenger_params IS NULL OR jsonb_typeof(challenger_params) = 'object'),
          backtest_scores JSONB NOT NULL CHECK (jsonb_typeof(backtest_scores) = 'object'),
          verdict TEXT NOT NULL CHECK (verdict = btrim(verdict) AND verdict <> ''),
          tie_break_applied JSONB NOT NULL
            CHECK (jsonb_typeof(tie_break_applied) = 'object'),
          cost_refs JSONB NOT NULL DEFAULT '[]'::jsonb
            CHECK (jsonb_typeof(cost_refs) = 'array'),
          started_at TIMESTAMPTZ NOT NULL,
          completed_at TIMESTAMPTZ NOT NULL,
          CHECK (corpus_size <= corpus_max_size),
          CHECK (completed_at >= started_at)
        )
        """
    )
    op.execute(
        "CREATE INDEX optimization_run_loop_completed_idx "
        "ON optimization_run (loop, completed_at, run_uid)"
    )
    op.execute(
        "CREATE INDEX optimization_run_trigger_thread_idx "
        "ON optimization_run (trigger_thread_id, completed_at) "
        "WHERE trigger_thread_id IS NOT NULL"
    )
    op.execute(
        """
        CREATE TABLE optimization_run_adoption (
          run_uid TEXT PRIMARY KEY REFERENCES optimization_run(run_uid),
          tap_event_uid TEXT NOT NULL REFERENCES scorer_activation(event_uid),
          adopted_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION optimization_history_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'optimization history is append-only';
        END
        $$
        """
    )
    for table in ("optimization_run", "optimization_run_adoption"):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION optimization_history_reject_mutation()"
        )


def downgrade() -> None:
    for table in ("optimization_run_adoption", "optimization_run"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION optimization_history_reject_mutation()")
    op.execute("DROP TABLE optimization_run_adoption")
    op.execute("DROP TABLE optimization_run")
