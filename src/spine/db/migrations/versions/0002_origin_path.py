"""Add inert workspace-relative origin metadata to memory heads.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable origin-path metadata without changing scorer behavior."""

    op.execute("ALTER TABLE memory_unit ADD COLUMN origin_path TEXT")


def downgrade() -> None:
    """Remove only the metadata column owned by this migration."""

    op.execute("ALTER TABLE memory_unit DROP COLUMN origin_path")
