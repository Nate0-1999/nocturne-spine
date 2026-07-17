"""Create the authoritative SPEC C.2 schema and seed scorer v0.

Revision ID: 0001
Revises:
Create Date: 2026-07-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _execute(sql: str) -> None:
    """Execute the authoritative SQL literally, including JSON colons."""

    op.get_bind().exec_driver_sql(sql)


def upgrade() -> None:
    """Apply the full literal C.2 DDL, then seed the C.3 v0 scorer."""

    _execute("CREATE EXTENSION IF NOT EXISTS vector")

    _execute(
        """
        CREATE TABLE memory_unit (
          id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          principal_id  TEXT NOT NULL,
          label         TEXT NOT NULL,
          body          TEXT NOT NULL,
          kind          TEXT NOT NULL CHECK (kind IN
                        ('fact','preference','procedure','project_note','persona','pinned')),
          keywords      TEXT[] NOT NULL DEFAULT '{}',
          embedding     vector(1536) NOT NULL,
          embedding_model TEXT NOT NULL,
          project_key   TEXT,
          thread_origin TEXT,
          pin           BOOLEAN NOT NULL DEFAULT FALSE,
          status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN
                        ('active','quarantined','tombstoned')),
          revision      INTEGER NOT NULL DEFAULT 1,
          stats         JSONB NOT NULL DEFAULT
                        '{"injections":0,"removals":0,"citations":0,"never_kills":0,"last_injected_at":null}',
          bias          REAL NOT NULL DEFAULT 0.0,
          created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    _execute("CREATE INDEX ON memory_unit USING hnsw (embedding vector_cosine_ops)")
    _execute("CREATE INDEX ON memory_unit (principal_id, status, project_key)")

    _execute(
        """
        CREATE TABLE memory_revision (
          rev_uid     TEXT PRIMARY KEY,
          parent_uid  TEXT REFERENCES memory_revision(rev_uid),
          memory_id   UUID NOT NULL REFERENCES memory_unit(id),
          revision    INTEGER,
          body        TEXT NOT NULL,
          label       TEXT NOT NULL,
          editor      TEXT NOT NULL,
          origin_machine_id TEXT NOT NULL,
          reason      TEXT NOT NULL DEFAULT '',
          ts          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    _execute("CREATE INDEX ON memory_revision (memory_id, ts)")

    _execute(
        """
        CREATE TABLE thread (
          id              UUID PRIMARY KEY,
          principal_id    TEXT NOT NULL,
          agent_id        TEXT NOT NULL,
          machine_id      TEXT NOT NULL,
          project_key     TEXT,
          snapshot_ts     TIMESTAMPTZ,
          created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    _execute(
        """
        CREATE TABLE injection_event (
          id            BIGSERIAL PRIMARY KEY,
          event_uid     TEXT NOT NULL UNIQUE,
          injection_id  UUID NOT NULL,
          thread_id     UUID NOT NULL,
          agent_id      TEXT NOT NULL,
          machine_id    TEXT NOT NULL,
          principal_id  TEXT NOT NULL,
          project_key   TEXT,
          agent_kind    TEXT NOT NULL DEFAULT 'general',
          prompt_text   TEXT NOT NULL,
          scorer_version TEXT NOT NULL,
          memory_id     UUID NOT NULL,
          memory_kind   TEXT NOT NULL,
          features      JSONB NOT NULL,
          score         REAL NOT NULL,
          rank          INTEGER NOT NULL,
          shown_as      TEXT NOT NULL CHECK (shown_as IN ('injected','near_miss','pinned')),
          outcome       TEXT,
          ts            TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    _execute("CREATE INDEX ON injection_event (injection_id)")

    _execute(
        """
        CREATE TABLE scorer_config (
          version     TEXT PRIMARY KEY,
          weights     JSONB NOT NULL,
          params      JSONB NOT NULL,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
          active      BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )
    _execute(
        """
        INSERT INTO scorer_config (version, weights, params, active)
        VALUES (
          'v0',
          '{"sem":0.42,"kw":0.16,"time":0.11,"proj":0.16,"freq":0.08,"hist":0.07}'::jsonb,
          '{"tau":0.55,"top_k":8,"near_miss_k":3,"budget_tokens":3000,"budget_pct":0.05,"half_life_time_days":14,"half_life_hist_days":7,"never_bias_step":-0.15,"quarantine_kills":3,"candidate_pool":50}'::jsonb,
          TRUE
        )
        """
    )


def downgrade() -> None:
    """Remove only objects owned by this migration, in dependency order."""

    _execute("DROP TABLE scorer_config")
    _execute("DROP TABLE injection_event")
    _execute("DROP TABLE thread")
    _execute("DROP TABLE memory_revision")
    _execute("DROP TABLE memory_unit")
