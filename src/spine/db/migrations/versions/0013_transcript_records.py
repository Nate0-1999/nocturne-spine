"""Add the append-only A-057 transcript resurrection projection.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE transcript_record (
          principal_id TEXT NOT NULL CONSTRAINT transcript_record_principal_check
                       CHECK (principal_id = btrim(principal_id) AND principal_id <> ''),
          thread_id UUID NOT NULL,
          sequence BIGINT NOT NULL CONSTRAINT transcript_record_sequence_check
                   CHECK (sequence > 0),
          journal_line TEXT NOT NULL,
          sha256 TEXT NOT NULL CONSTRAINT transcript_record_sha256_check
                 CHECK (sha256 ~ '^[0-9a-f]{64}$'),
          received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (principal_id, thread_id, sequence)
        )
        """
    )
    op.execute(
        "CREATE INDEX transcript_record_received_at_idx "
        "ON transcript_record (principal_id, received_at)"
    )
    op.execute(
        """
        CREATE FUNCTION transcript_record_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'transcript_record is append-only';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER transcript_record_append_only
        BEFORE UPDATE OR DELETE ON transcript_record
        FOR EACH ROW EXECUTE FUNCTION transcript_record_reject_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER transcript_record_append_only ON transcript_record")
    op.execute("DROP FUNCTION transcript_record_reject_mutation()")
    op.execute("DROP TABLE transcript_record")
