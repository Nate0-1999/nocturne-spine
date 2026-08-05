"""Add the append-only M2M broker reconciliation journal.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE spend_reconciliation (
          event_uid                 TEXT PRIMARY KEY,
          ts                        TIMESTAMPTZ NOT NULL DEFAULT now(),
          provider                  TEXT NOT NULL CHECK (provider = 'openrouter'),
          status                    TEXT NOT NULL CHECK (
            status IN ('baseline','balanced','drift','unavailable')
          ),
          broker_usage_usd          NUMERIC(20,12),
          ledger_cost_usd           NUMERIC(20,12),
          broker_since_baseline_usd NUMERIC(20,12),
          ledger_since_baseline_usd NUMERIC(20,12),
          drift_usd                 NUMERIC(20,12),
          tolerance_usd             NUMERIC(20,12) NOT NULL CHECK (tolerance_usd >= 0),
          unpriced_lines            BIGINT NOT NULL CHECK (unpriced_lines >= 0),
          error_code                TEXT CHECK (
            error_code IS NULL OR error_code IN (
              'broker_unavailable','invalid_broker_response'
            )
          ),
          CONSTRAINT spend_reconciliation_shape_check CHECK (
            (
              status = 'unavailable'
              AND broker_usage_usd IS NULL
              AND ledger_cost_usd IS NULL
              AND broker_since_baseline_usd IS NULL
              AND ledger_since_baseline_usd IS NULL
              AND drift_usd IS NULL
              AND error_code IS NOT NULL
            ) OR (
              status = 'baseline'
              AND broker_usage_usd IS NOT NULL
              AND ledger_cost_usd IS NOT NULL
              AND broker_since_baseline_usd = 0
              AND ledger_since_baseline_usd = 0
              AND drift_usd = 0
              AND error_code IS NULL
            ) OR (
              status IN ('balanced','drift')
              AND broker_usage_usd IS NOT NULL
              AND ledger_cost_usd IS NOT NULL
              AND broker_since_baseline_usd IS NOT NULL
              AND ledger_since_baseline_usd IS NOT NULL
              AND drift_usd IS NOT NULL
              AND error_code IS NULL
            )
          )
        )
        """
    )
    op.execute("CREATE INDEX spend_reconciliation_ts_idx ON spend_reconciliation (ts, event_uid)")
    op.execute(
        """
        CREATE FUNCTION spend_reconciliation_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'spend_reconciliation is append-only';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER spend_reconciliation_append_only
        BEFORE UPDATE OR DELETE ON spend_reconciliation
        FOR EACH ROW EXECUTE FUNCTION spend_reconciliation_reject_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER spend_reconciliation_append_only ON spend_reconciliation")
    op.execute("DROP FUNCTION spend_reconciliation_reject_mutation()")
    op.execute("DROP TABLE spend_reconciliation")
