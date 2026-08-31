"""Add a durable removal-pressure trigger to curator cadence.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-31
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE curator_trigger_state ADD COLUMN pressure_events BIGINT NOT NULL "
        "DEFAULT 0 CHECK (pressure_events >= 0)"
    )
    op.execute(
        "ALTER TABLE curator_trigger_state ADD COLUMN last_run_pressure BIGINT NOT NULL "
        "DEFAULT 0 CHECK (last_run_pressure >= 0 AND last_run_pressure <= pressure_events)"
    )
    op.execute(
        """
        WITH pressure AS (
          SELECT principal_id,
                 sum(GREATEST(COALESCE((stats->>'removals')::bigint, 0), 0)) AS total
          FROM memory_unit
          WHERE status = 'active'
          GROUP BY principal_id
        )
        UPDATE curator_trigger_state AS state
        SET pressure_events = pressure.total,
            last_run_pressure = pressure.total
        FROM pressure
        WHERE pressure.principal_id = state.principal_id
        """
    )
    op.execute(
        "ALTER TABLE curator_run ADD COLUMN pressure_snapshot BIGINT NOT NULL "
        "DEFAULT 0 CHECK (pressure_snapshot >= 0)"
    )
    op.execute("ALTER TABLE curator_run ALTER COLUMN pressure_snapshot DROP DEFAULT")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION nocturne_tick_curator_write() RETURNS trigger AS $$
        DECLARE
          write_delta BIGINT := 0;
          pressure_delta BIGINT := 0;
        BEGIN
          IF NEW.status = 'active'
             AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'active') THEN
            write_delta := 1;
          END IF;
          IF TG_OP = 'UPDATE' AND NEW.status = 'active' THEN
            pressure_delta := GREATEST(
              COALESCE((NEW.stats->>'removals')::bigint, 0)
              - COALESCE((OLD.stats->>'removals')::bigint, 0),
              0
            );
          END IF;
          IF write_delta > 0 OR pressure_delta > 0 THEN
            INSERT INTO curator_trigger_state (
              principal_id, admitted_writes, last_run_writes,
              pressure_events, last_run_pressure
            )
            VALUES (NEW.principal_id, write_delta, 0, pressure_delta, 0)
            ON CONFLICT (principal_id) DO UPDATE
              SET admitted_writes = curator_trigger_state.admitted_writes + write_delta,
                  pressure_events = curator_trigger_state.pressure_events + pressure_delta,
                  updated_at = now();
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER memory_unit_curator_write_tick ON memory_unit")
    op.execute(
        "CREATE TRIGGER memory_unit_curator_write_tick "
        "AFTER INSERT OR UPDATE OF status, stats ON memory_unit "
        "FOR EACH ROW EXECUTE FUNCTION nocturne_tick_curator_write()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER memory_unit_curator_write_tick ON memory_unit")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION nocturne_tick_curator_write() RETURNS trigger AS $$
        BEGIN
          IF NEW.status = 'active'
             AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM 'active') THEN
            INSERT INTO curator_trigger_state (principal_id, admitted_writes, last_run_writes)
            VALUES (NEW.principal_id, 1, 0)
            ON CONFLICT (principal_id) DO UPDATE
              SET admitted_writes = curator_trigger_state.admitted_writes + 1,
                  updated_at = now();
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER memory_unit_curator_write_tick "
        "AFTER INSERT OR UPDATE OF status ON memory_unit "
        "FOR EACH ROW EXECUTE FUNCTION nocturne_tick_curator_write()"
    )
    op.execute("ALTER TABLE curator_run DROP COLUMN pressure_snapshot")
    op.execute("ALTER TABLE curator_trigger_state DROP COLUMN last_run_pressure")
    op.execute("ALTER TABLE curator_trigger_state DROP COLUMN pressure_events")
