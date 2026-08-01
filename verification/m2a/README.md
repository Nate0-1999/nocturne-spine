# M2A — Spend ledger core evidence

Date: 2026-08-01
Session: `codex / 2026-08-01 / a4d2`

## Authoritative storage

- Alembic `0003` creates append-only `spend_event` in receipt-line normal form.
- UPDATE and DELETE are rejected by the database trigger
  `spend_event_append_only`.
- Bearer-protected `POST /v1/spend/events` atomically accepts nonempty
  `llm.request` / `llm.embedding` batches. An equal `event_uid` replay is a
  success; a differing replay is an RFC7807 409 with no partial insert.
- SQL COMMENTs ship the receipt-language glossary on the table, every column,
  and every canonical materialized view.
- `v_spend_rate`, `v_thread_cost`, `v_run_cost`, `v_memory_cost`, and
  `v_cache_efficiency` refresh on the production minute loop and remain derived
  lenses over `spend_event`.

## Provider write path

The production OpenAI-compatible embedding adapter retains provider usage,
native cost, model/provider, and response/request id, then writes its nonzero
`llm.embedding` receipt through the in-process SpendService before releasing
the vector. Missing provider quantity emits no synthetic zero line; missing
cost remains NULL.

## Verification

`tests/test_spend.py` proves atomicity, equal replay, conflicting replay,
append-only enforcement, canonical view refresh, double-run byte determinism,
cache-efficiency arithmetic, and database glossary comments.
`tests/test_embeddings.py` proves synchronous embedding receipt success and
fail-closed receipt failure. `tests/test_db.py` proves the ORM and migrated
PostgreSQL schema have no drift. `tests/test_api.py` pins the generated OpenAPI
contract.

Final local commands:

```text
.venv/bin/ruff check .
All checks passed!

TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock \
TESTCONTAINERS_RYUK_DISABLED=true PYTHONPATH=src .venv/bin/pytest -q
174 passed
```

The seeded row's acceptance sentence is:

> building bought 125.000000000 tokens of input_fresh for llm.request on
> anthropic/claude-sonnet-4.6 from anthropic, costing $0.000250000000
> (measured), ref gen-test-1.

## Explicit exclusions

No GCP billing reconciliation, `infra.*` producer, invoice mutation, BigQuery
resource, dashboard, spend wall, or wave-2 self-audit was built.
