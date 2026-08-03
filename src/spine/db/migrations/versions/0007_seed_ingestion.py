"""Add M2I seed birthplace batches and split kinship.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_edge DROP CONSTRAINT memory_edge_edge_type_check")
    op.execute(
        "ALTER TABLE memory_edge ADD CONSTRAINT memory_edge_edge_type_check "
        "CHECK (edge_type IN ('merged_from','supersedes','contradicts','relates_to'))"
    )
    op.execute("ALTER TABLE approval_queue_item ALTER COLUMN birthplace_thread_id DROP NOT NULL")
    op.execute(
        "ALTER TABLE approval_queue_item ADD COLUMN birthplace TEXT NOT NULL DEFAULT 'thread'"
    )
    op.execute("ALTER TABLE approval_queue_item ADD COLUMN batch_uid UUID")
    op.execute("ALTER TABLE approval_queue_item ADD COLUMN source_name TEXT")
    op.execute("ALTER TABLE approval_queue_item ADD COLUMN source_sha256 TEXT")
    op.execute(
        "ALTER TABLE approval_queue_item ADD CONSTRAINT approval_queue_item_birthplace_check "
        "CHECK (birthplace IN ('thread','seed'))"
    )
    op.execute(
        "ALTER TABLE approval_queue_item ADD CONSTRAINT approval_queue_item_birthplace_shape_check "
        "CHECK ((birthplace = 'thread' AND birthplace_thread_id IS NOT NULL "
        "AND batch_uid IS NULL AND source_name IS NULL AND source_sha256 IS NULL) OR "
        "(birthplace = 'seed' AND birthplace_thread_id IS NULL AND batch_uid IS NOT NULL "
        "AND source_name IS NOT NULL AND source_sha256 IS NOT NULL))"
    )
    op.execute(
        "CREATE INDEX approval_queue_item_batch_state_idx "
        "ON approval_queue_item (batch_uid, state)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX approval_queue_item_batch_state_idx")
    op.execute(
        "ALTER TABLE approval_queue_item DROP CONSTRAINT approval_queue_item_birthplace_shape_check"
    )
    op.execute(
        "ALTER TABLE approval_queue_item DROP CONSTRAINT approval_queue_item_birthplace_check"
    )
    op.execute("ALTER TABLE approval_queue_item DROP COLUMN source_sha256")
    op.execute("ALTER TABLE approval_queue_item DROP COLUMN source_name")
    op.execute("ALTER TABLE approval_queue_item DROP COLUMN batch_uid")
    op.execute("ALTER TABLE approval_queue_item DROP COLUMN birthplace")
    op.execute("ALTER TABLE approval_queue_item ALTER COLUMN birthplace_thread_id SET NOT NULL")
    op.execute("ALTER TABLE memory_edge DROP CONSTRAINT memory_edge_edge_type_check")
    op.execute(
        "ALTER TABLE memory_edge ADD CONSTRAINT memory_edge_edge_type_check "
        "CHECK (edge_type IN ('merged_from','supersedes','contradicts'))"
    )
