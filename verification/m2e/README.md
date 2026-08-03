# M2E — Hybrid candidate retrieval evidence

Date: 2026-08-02
Session: `codex / 2026-08-02 / c2a4`

## Delivered boundary

- Alembic `0004` adds a non-null `TSVECTOR` over memory label, body, and
  keywords, maintained by a tamper-overwriting trigger and indexed with GIN.
- `inject/prepare` retrieves the deduplicated union of the exact vector top-50
  and FTS top-50. The lexical leg ORs scorer-normalized prompt terms and orders
  by `ts_rank_cd DESC, memory_id ASC`.
- Vector membership materializes every eligible ID and cosine distance before
  applying C.3's exact distance/UUID boundary. This deliberately avoids HNSW's
  approximate cutoff for the owner-scale gate path.
- The scorer ranks every member of that already-bounded union without changing
  its six features, formula, threshold, pin law, ordering, or token budget.
- Persisted event metadata records canonical retrieval sources under
  `_retrieval.sources`; the public card remains the exact six-feature shape.

## Acceptance proofs

- `test_exact_keyword_with_weak_embedding_reaches_the_gate_via_fts` plants 50
  stronger-vector decoys plus one orthogonal, exact-keyword memory. The target
  is excluded from the vector pool, scores `0.58` under unchanged scorer v0,
  reaches injection, and persists `sources=["fts"]`.
- `test_hybrid_pool_uses_or_terms_and_exact_uuid_tie_boundaries` disables the
  small-table sequential-scan happy path, plants 51 equal vector/FTS matches in
  reverse order, and proves both legs return the lower 50 UUIDs with one
  deduplicated `sources=["vector","fts"]` membership each.
- Existing prepare and pin tests prove dual-source overlap yields one card and
  event, eligibility filters apply to both legs, pins record `pinned`, and
  `_retrieval` never enters the public feature object.
- Migration tests exercise a real `0003 -> 0004` legacy-row backfill, label /
  body / keyword matching, insert and update refresh, direct derived-column
  tamper overwrite, GIN metadata, downgrade, and re-upgrade.
- The pure scorer regression proves `candidate_pool` is retrieval-owned and
  every supplied union member is scored before unchanged threshold/budget
  selection.

## Final verification

```text
uv run --locked ruff check .
All checks passed!

TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock \
TESTCONTAINERS_RYUK_DISABLED=true PYTHONPATH=src uv run --locked pytest -q
177 passed in 6.00s

PYTHONPATH=src uv run --locked pytest -q -m 'not contract'  # Harness
549 passed, 3 deselected in 1.72s

uv build
Successfully built dist/nocturne_spine-0.1.0.tar.gz
Successfully built dist/nocturne_spine-0.1.0-py3-none-any.whl

scripts/verify_wheel.py  # from an isolated install of the built wheel
nocturne-spine installed-wheel smoke passed
```

`git diff --check` passed. Three independent read-only reviews covered the
query/scorer seam, migration lifecycle, and acceptance-test sufficiency. The
final adversarial pass found the original HNSW/default-40 risk; the exact
materialized vector boundary above closed it, and two re-reviews reported no
remaining finding.

## Explicit exclusions

No scorer-weight change, learning behavior, public API field, UI, graph edge,
runtime configuration surface, or non-M2E search behavior was added.
