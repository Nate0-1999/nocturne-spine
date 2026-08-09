"""Permit first-class budget-cut injection events.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-09
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("injection_event_shown_as_check", "injection_event", type_="check")
    op.create_check_constraint(
        "injection_event_shown_as_check",
        "injection_event",
        "shown_as IN ('injected','near_miss','pinned','budget_cut')",
    )


def downgrade() -> None:
    op.execute("UPDATE injection_event SET shown_as = 'near_miss' WHERE shown_as = 'budget_cut'")
    op.drop_constraint("injection_event_shown_as_check", "injection_event", type_="check")
    op.create_check_constraint(
        "injection_event_shown_as_check",
        "injection_event",
        "shown_as IN ('injected','near_miss','pinned')",
    )
