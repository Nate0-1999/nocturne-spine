"""Add the ADR-024 append-only spend ledger and canonical views.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create receipt-line normal form and its non-authoritative lenses."""

    op.execute(
        """
        CREATE TABLE spend_event (
          event_uid TEXT PRIMARY KEY,
          ts TIMESTAMPTZ NOT NULL,
          product_type TEXT NOT NULL,
          quantity_type TEXT NOT NULL,
          unit_of_measure TEXT NOT NULL,
          quantity NUMERIC(30,9) NOT NULL,
          cost_usd NUMERIC(20,12),
          basis TEXT NOT NULL,
          behavior TEXT NOT NULL,
          purpose TEXT NOT NULL,
          principal_id TEXT,
          machine_id TEXT,
          origin_agent TEXT,
          thread_id UUID,
          run_id TEXT,
          prompt_id TEXT,
          memory_id UUID,
          model TEXT,
          provider TEXT,
          quantization TEXT,
          ref TEXT NOT NULL,
          meta JSONB NOT NULL DEFAULT '{}'::jsonb,
          CONSTRAINT spend_event_product_type_check
            CHECK (
              product_type IN (
                'llm.request','llm.embedding','llm.fee','infra.db.instance',
                'infra.db.storage','infra.run.serve','infra.run.job',
                'infra.observability','net.egress','fleet.lease','fleet.snapshot'
              ) OR product_type LIKE 'ext.api._%'
            ),
          CONSTRAINT spend_event_quantity_type_nonblank_check
            CHECK (quantity_type = btrim(quantity_type) AND quantity_type <> ''),
          CONSTRAINT spend_event_unit_of_measure_nonblank_check
            CHECK (unit_of_measure = btrim(unit_of_measure) AND unit_of_measure <> ''),
          CONSTRAINT spend_event_quantity_check CHECK (quantity > 0),
          CONSTRAINT spend_event_cost_usd_check CHECK (cost_usd IS NULL OR cost_usd >= 0),
          CONSTRAINT spend_event_basis_check
            CHECK (basis IN ('measured','allocated','estimated')),
          CONSTRAINT spend_event_behavior_check
            CHECK (behavior IN ('variable','fixed','step')),
          CONSTRAINT spend_event_purpose_check
            CHECK (purpose IN (
              'building','extraction','curation','judge','remember','embedding','scout'
            )),
          CONSTRAINT spend_event_ref_nonblank_check
            CHECK (ref = btrim(ref) AND ref <> '')
        )
        """
    )
    op.execute("CREATE INDEX spend_event_ts_idx ON spend_event (ts)")
    op.execute("CREATE INDEX spend_event_ref_idx ON spend_event (ref)")
    op.execute("CREATE INDEX spend_event_thread_id_idx ON spend_event (thread_id)")
    op.execute("CREATE INDEX spend_event_run_id_idx ON spend_event (run_id)")
    op.execute("CREATE INDEX spend_event_memory_id_idx ON spend_event (memory_id)")

    op.execute(
        """
        CREATE FUNCTION spend_event_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'spend_event is append-only';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER spend_event_append_only
        BEFORE UPDATE OR DELETE ON spend_event
        FOR EACH ROW EXECUTE FUNCTION spend_event_reject_mutation()
        """
    )

    op.execute(
        """
        COMMENT ON TABLE spend_event IS
          'LEDGER receipt line: one immutable sentence for one purchased price class.'
        """
    )
    _comment("event_uid", "ULID receipt identity; its leading bits carry the purchase timestamp.")
    _comment("ts", "When the provider purchase completed, with timezone.")
    _comment("product_type", "What was bought: in M2A, an LLM request or embedding.")
    _comment(
        "quantity_type",
        "The price class bought: fresh input, cached input, cache write, output, or reasoning.",
    )
    _comment("unit_of_measure", "The noun attached to quantity; M2A uses tokens.")
    _comment("quantity", "How many units were bought; receipt lines never pad with zero units.")
    _comment(
        "cost_usd",
        "Native broker dollars for this line, NULL when the bill has not supplied a cost.",
    )
    _comment(
        "basis",
        "Honesty column: measured, allocated, or estimated; allocation is never measurement.",
    )
    _comment(
        "behavior",
        "Cost lever: variable per action, fixed baseline, or step capacity jump.",
    )
    _comment(
        "purpose",
        "Why bought: building, extraction, curation, judge, remember, embedding, or scout.",
    )
    _comment("principal_id", "Human funding lineage, when known.")
    _comment("machine_id", "Machine lineage, when known.")
    _comment("origin_agent", "Agent path lineage; prefixes roll up a sub-agent subtree.")
    _comment("thread_id", "Conversation grain; GROUP BY this column is thread cost.")
    _comment("run_id", "Run grain; GROUP BY this column is run cost.")
    _comment("prompt_id", "Query grain shared by its model and embedding purchases.")
    _comment("memory_id", "Memory grain enabling future cost-per-citation economics.")
    _comment("model", "Executable model identity reported for the purchase.")
    _comment("provider", "Downstream inference provider when known; otherwise the direct provider.")
    _comment(
        "quantization",
        "Endpoint precision when the broker reports it; NULL is honest unknown.",
    )
    _comment("ref", "Provider response or generation id joining every price class of one request.")
    _comment(
        "meta",
        "Replay-safe provider detail and allocation provenance not promoted to a column.",
    )

    op.execute(
        """
        CREATE MATERIALIZED VIEW v_spend_rate AS
        SELECT date_trunc('minute', ts) AS minute,
               purpose,
               model,
               provider,
               count(*)::BIGINT AS receipt_lines,
               sum(quantity) AS quantity,
               sum(cost_usd) AS cost_usd,
               count(*) FILTER (WHERE cost_usd IS NULL)::BIGINT AS unpriced_lines
          FROM spend_event
         GROUP BY date_trunc('minute', ts), purpose, model, provider
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW v_thread_cost AS
        SELECT thread_id,
               count(*)::BIGINT AS receipt_lines,
               sum(quantity) AS quantity,
               sum(cost_usd) AS cost_usd,
               count(*) FILTER (WHERE cost_usd IS NULL)::BIGINT AS unpriced_lines,
               min(ts) AS first_spend_at,
               max(ts) AS last_spend_at
          FROM spend_event
         WHERE thread_id IS NOT NULL
         GROUP BY thread_id
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW v_run_cost AS
        SELECT run_id,
               thread_id,
               count(*)::BIGINT AS receipt_lines,
               sum(quantity) AS quantity,
               sum(cost_usd) AS cost_usd,
               count(*) FILTER (WHERE cost_usd IS NULL)::BIGINT AS unpriced_lines,
               min(ts) AS first_spend_at,
               max(ts) AS last_spend_at
          FROM spend_event
         WHERE run_id IS NOT NULL
         GROUP BY run_id, thread_id
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW v_memory_cost AS
        SELECT memory_id,
               count(*)::BIGINT AS receipt_lines,
               sum(quantity) AS quantity,
               sum(cost_usd) AS cost_usd,
               count(*) FILTER (WHERE cost_usd IS NULL)::BIGINT AS unpriced_lines,
               min(ts) AS first_spend_at,
               max(ts) AS last_spend_at
          FROM spend_event
         WHERE memory_id IS NOT NULL
         GROUP BY memory_id
        """
    )
    op.execute(
        """
        CREATE MATERIALIZED VIEW v_cache_efficiency AS
        SELECT date_trunc('minute', ts) AS minute,
               model,
               provider,
               sum(quantity) FILTER (WHERE quantity_type = 'input_cached') AS cached_tokens,
               sum(quantity) FILTER (WHERE quantity_type = 'input_fresh') AS fresh_tokens,
               CASE
                 WHEN sum(quantity) FILTER (
                        WHERE quantity_type IN ('input_cached','input_fresh')
                      ) > 0
                 THEN coalesce(sum(quantity) FILTER (
                        WHERE quantity_type = 'input_cached'
                      ), 0) / sum(quantity) FILTER (
                        WHERE quantity_type IN ('input_cached','input_fresh')
                      )
                 ELSE NULL
               END AS cache_efficiency
          FROM spend_event
         WHERE product_type = 'llm.request'
           AND quantity_type IN ('input_cached','input_fresh')
         GROUP BY date_trunc('minute', ts), model, provider
        """
    )
    op.execute(
        """
        COMMENT ON MATERIALIZED VIEW v_spend_rate IS
          'VITALS minute spend lanes; derived, never authoritative.'
        """
    )
    op.execute(
        """
        COMMENT ON MATERIALIZED VIEW v_thread_cost IS
          'Thread-grain cost lens over immutable receipt lines; derived, never authoritative.'
        """
    )
    op.execute(
        """
        COMMENT ON MATERIALIZED VIEW v_run_cost IS
          'Run-grain cost lens over immutable receipt lines; derived, never authoritative.'
        """
    )
    op.execute(
        """
        COMMENT ON MATERIALIZED VIEW v_memory_cost IS
          'Memory-grain cost lens for future cost-per-citation; derived, never authoritative.'
        """
    )
    op.execute(
        """
        COMMENT ON MATERIALIZED VIEW v_cache_efficiency IS
          'Cached divided by cached-plus-fresh input tokens; derived, never authoritative.'
        """
    )


def downgrade() -> None:
    """Remove only the M2A ledger objects."""

    for view in (
        "v_cache_efficiency",
        "v_memory_cost",
        "v_run_cost",
        "v_thread_cost",
        "v_spend_rate",
    ):
        op.execute(f"DROP MATERIALIZED VIEW {view}")
    op.execute("DROP TRIGGER spend_event_append_only ON spend_event")
    op.execute("DROP FUNCTION spend_event_reject_mutation()")
    op.execute("DROP TABLE spend_event")


def _comment(column: str, description: str) -> None:
    escaped = description.replace("'", "''")
    op.execute(f"COMMENT ON COLUMN spend_event.{column} IS '{escaped}'")
