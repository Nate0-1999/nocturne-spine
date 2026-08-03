"""Add M2H candidate queue, decisions, and verdict edges.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_unit DROP CONSTRAINT memory_unit_status_check")
    op.execute(
        "ALTER TABLE memory_unit ADD CONSTRAINT memory_unit_status_check "
        "CHECK (status IN ('active','candidate','quarantined','tombstoned'))"
    )
    statements = (
        """
        CREATE TABLE memory_edge (
          edge_uid TEXT PRIMARY KEY,
          from_memory_id UUID NOT NULL REFERENCES memory_unit(id),
          to_memory_id UUID NOT NULL REFERENCES memory_unit(id),
          edge_type TEXT NOT NULL CHECK (edge_type IN ('merged_from','supersedes','contradicts')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (from_memory_id, to_memory_id, edge_type)
        )
        """,
        """
        CREATE TABLE approval_queue_item (
          item_uid TEXT PRIMARY KEY,
          candidate_memory_id UUID NOT NULL UNIQUE REFERENCES memory_unit(id),
          principal_id TEXT NOT NULL,
          birthplace_thread_id UUID NOT NULL,
          verdict TEXT NOT NULL CHECK (verdict IN ('new','merge','supersede','contradict')),
          neighbor_ids JSONB NOT NULL,
          target_ids JSONB NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','approved','rejected')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          decided_at TIMESTAMPTZ
        )
        """,
        "CREATE INDEX approval_queue_item_principal_state_idx "
        "ON approval_queue_item (principal_id, state)",
        "CREATE INDEX approval_queue_item_thread_state_idx "
        "ON approval_queue_item (birthplace_thread_id, state)",
        """
        CREATE TABLE approval_decision (
          decision_uid TEXT PRIMARY KEY,
          item_uid TEXT NOT NULL UNIQUE REFERENCES approval_queue_item(item_uid),
          decision TEXT NOT NULL CHECK (decision IN ('approve','deny')),
          approval_mode TEXT NOT NULL CHECK (approval_mode IN ('explicit','passive')),
          actor_class TEXT NOT NULL CHECK (actor_class IN ('human','passive')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
    )
    for statement in statements:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE approval_decision")
    op.execute("DROP TABLE approval_queue_item")
    op.execute("DROP TABLE memory_edge")
    op.execute("ALTER TABLE memory_unit DROP CONSTRAINT memory_unit_status_check")
    op.execute(
        "ALTER TABLE memory_unit ADD CONSTRAINT memory_unit_status_check "
        "CHECK (status IN ('active','quarantined','tombstoned'))"
    )
