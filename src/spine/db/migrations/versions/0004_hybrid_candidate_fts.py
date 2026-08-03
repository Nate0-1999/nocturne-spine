"""Add the indexed lexical leg of M2E hybrid candidate retrieval.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill and maintain one GIN-indexed simple-dictionary tsvector."""

    op.execute("ALTER TABLE memory_unit ADD COLUMN search_tsv TSVECTOR")
    op.execute(
        """
        UPDATE memory_unit
           SET search_tsv = to_tsvector(
             'pg_catalog.simple'::regconfig,
             label || ' ' || body || ' ' || coalesce(array_to_string(keywords, ' '), '')
           )
        """
    )
    op.execute("ALTER TABLE memory_unit ALTER COLUMN search_tsv SET NOT NULL")
    op.execute(
        """
        CREATE FUNCTION memory_unit_refresh_search_tsv() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          NEW.search_tsv := to_tsvector(
            'pg_catalog.simple'::regconfig,
            NEW.label || ' ' || NEW.body || ' '
              || coalesce(array_to_string(NEW.keywords, ' '), '')
          );
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER memory_unit_refresh_search_tsv
        BEFORE INSERT OR UPDATE OF label, body, keywords, search_tsv ON memory_unit
        FOR EACH ROW EXECUTE FUNCTION memory_unit_refresh_search_tsv()
        """
    )
    op.execute("CREATE INDEX memory_unit_search_tsv_idx ON memory_unit USING gin (search_tsv)")
    op.execute(
        "COMMENT ON COLUMN memory_unit.search_tsv IS "
        "'M2E lexical candidate document over label, body, and keywords.'"
    )


def downgrade() -> None:
    """Remove the derived lexical document and its maintenance objects."""

    op.execute("DROP INDEX memory_unit_search_tsv_idx")
    op.execute("DROP TRIGGER memory_unit_refresh_search_tsv ON memory_unit")
    op.execute("DROP FUNCTION memory_unit_refresh_search_tsv()")
    op.execute("ALTER TABLE memory_unit DROP COLUMN search_tsv")
