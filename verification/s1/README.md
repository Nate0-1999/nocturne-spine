# S1 DB layer and CAS evidence

This is packet evidence, not the independent M1 verdict reserved by SPEC B.6.
It records how to reproduce the C.2 model, concurrency, history, and tombstone
checks delivered by S1.

## Commands

From the Spine repository root:

```sh
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest
.githooks/pre-commit --all
```

On this workstation, macOS File Provider may repeatedly mark editable-install
`.pth` files hidden. When that happens, prefix Python commands with
`PYTHONPATH=src`; it changes no source or dependency behavior. The Docker
socket override is the existing Colima requirement recorded by P0.

## Recorded result — 2026-07-17

Ruff lint and formatting passed. Pytest used Python 3.12.9, started disposable
`pgvector/pgvector:pg16`, applied production migration `0001`, and completed:

```text
25 passed in 2.26s
```

The eight S1 checks in `tests/test_db.py` prove:

- all five declarative models have the exact C.2 table, column, PostgreSQL
  type, nullability, key, index, operator-class, and partial-index mapping,
  with Alembic reporting no metadata drift from the migrated database;
- two successful CAS writes advance `1 → 2 → 3` and append the exact
  `root → child → grandchild` `parent_uid` lineage with resulting body/label
  plus editor, machine, and reason attribution;
- two concurrent writers at revision 1 produce one revision-2 winner and one
  typed 409 conflict whose detached snapshot is the committed winner;
- a deliberately duplicated `rev_uid` makes the revision insert fail and the
  preceding head update roll back, leaving revision 1 and root-only history;
- a missing lineage row raises inside an internal savepoint, so even a caller
  that catches the application error inside its outer transaction cannot
  commit a head/history split;
- the helper rejects missing or implicit/autobegun transaction boundaries; a
  successful helper call followed by caller rollback persists neither table;
- caller-supplied revision IDs must have canonical ULID syntax without adding
  a server-side generator or dependency;
- tombstoning increments the head, appends history, preserves the original
  row, and releases its active label for a replacement unit.

The existing migration tests continue to prove the vector extension,
`vector(1536)`, exact `memory_unit_active_label` predicate, scorer `v0` seed,
and active-label collision at the database boundary. All seven C.4 routes
remain named RFC 7807 `501` stubs; S1 does not take S2's CRUD/HTTP work.
