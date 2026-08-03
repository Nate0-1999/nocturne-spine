"""Add actor provenance for M2G per-message injection events.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Classify existing gates as human and admit passive M2G batches."""

    op.execute("ALTER TABLE injection_event ADD COLUMN actor_class TEXT NOT NULL DEFAULT 'human'")
    op.execute(
        "ALTER TABLE injection_event ADD CONSTRAINT "
        "injection_event_actor_class_check "
        "CHECK (actor_class IN ('human','passive'))"
    )


def downgrade() -> None:
    """Remove M2G actor provenance."""

    op.execute("ALTER TABLE injection_event DROP CONSTRAINT injection_event_actor_class_check")
    op.execute("ALTER TABLE injection_event DROP COLUMN actor_class")
