"""Add the append-only A-053 injection-event hygiene overlay.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE injection_event_annotation (
          target_event_uid          TEXT PRIMARY KEY CONSTRAINT
                                    injection_event_annotation_target_event_uid_fkey
                                    REFERENCES injection_event(event_uid),
          kind                      TEXT NOT NULL CONSTRAINT
                                    injection_event_annotation_kind_check
                                    CHECK (kind = 'verification_only'),
          target_principal_id       TEXT NOT NULL,
          target_machine_id         TEXT NOT NULL,
          reason                    TEXT NOT NULL CONSTRAINT
                                    injection_event_annotation_reason_check CHECK (
            reason = btrim(reason) AND reason <> ''
          ),
          annotator_principal_id    TEXT NOT NULL CONSTRAINT
                                    injection_event_annotation_annotator_principal_check CHECK (
            annotator_principal_id = btrim(annotator_principal_id)
            AND annotator_principal_id <> ''
          ),
          annotator_machine_id      TEXT NOT NULL CONSTRAINT
                                    injection_event_annotation_annotator_machine_check CHECK (
            annotator_machine_id = btrim(annotator_machine_id)
            AND annotator_machine_id <> ''
          ),
          annotator_origin_agent    TEXT NOT NULL CONSTRAINT
                                    injection_event_annotation_annotator_agent_check CHECK (
            annotator_origin_agent = btrim(annotator_origin_agent)
            AND annotator_origin_agent <> ''
          ),
          ts                        TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION injection_event_annotation_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'injection_event_annotation is append-only';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER injection_event_annotation_append_only
        BEFORE UPDATE OR DELETE ON injection_event_annotation
        FOR EACH ROW EXECUTE FUNCTION injection_event_annotation_reject_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER injection_event_annotation_append_only ON injection_event_annotation")
    op.execute("DROP FUNCTION injection_event_annotation_reject_mutation()")
    op.execute("DROP TABLE injection_event_annotation")
