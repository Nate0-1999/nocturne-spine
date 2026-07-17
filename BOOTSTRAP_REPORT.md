# Spine Agent Zero bootstrap report

Status: **P0 v1.5 refresh complete and locally verified**

## What exists

- A standalone Python 3.12 repository with the C.1 package areas, a
  byte-for-byte frozen SPEC v1.5 at `docs/SPEC.md`, and both relay ground-rule
  files regenerated from Garden Plan §6.
- FastAPI app factory, static bearer middleware, RFC 7807 auth/validation/HTTP
  errors, and authenticated `/healthz` returning `{ok, version}`.
- Async SQLAlchemy/Alembic plumbing and migration `0001`, containing the full
  v1.5 C.2 DDL—including `memory_unit_active_label`—plus the active scorer `v0`
  seed from C.3.
- Strict request, query, success, and alternate-response schemas for the full
  v1.5 C.4 surface. The committed `openapi.json` exposes those schemas while
  the P0 runtime remains deliberately inert; prepare cards require concrete
  features/rank, while dedup/search cards require those fields to be null.
- A Python 3.12 image and Compose topology with `pgvector/pgvector:pg16` plus
  `spine`; the service applies Alembic before Uvicorn starts.
- Ruff/pytest CI, testcontainers migration evidence, and a tracked M1
  pre-commit scope fence repeated over all tracked files in CI.

## Human-gate resolutions now frozen

The v1.5 constitution and scaffold incorporate Garden F001–F005's accepted
resolution:

- active `(principal_id, label)` values are protected by the exact partial
  unique index; quarantine/tombstone frees the label;
- memory create carries `machine_id` and `force=false`, and patch carries
  `machine_id`;
- revision attribution is therefore available as `origin_machine_id`;
- commit responses include `wrong_removed: [MemoryUnit]`;
- `MemoryUnit`, create/PATCH alternatives, and list `limit`/`offset` paging are
  explicit response/query contracts.

No unresolved v1.4 seam remains in this repository. Decision 001 records the
historical P0 stop; Decision 003 records how the refreshed, typed OpenAPI stays
separate from later packets' behavior.

## What is deliberately stubbed

All seven C.4 routes are registered with exact v1.5 signatures but contain no
business logic. Every valid call returns `501 application/problem+json` and an
`endpoint` extension naming the stub:

1. `POST /v1/inject/prepare`
2. `POST /v1/inject/commit`
3. `POST /v1/feedback`
4. `POST /v1/memories`
5. `PATCH /v1/memories/{id}`
6. `GET /v1/memories`
7. `POST /v1/search`

There is no CRUD, embedding, scoring, injection, feedback, event-writing,
learning, maintenance, extraction, relay, presence, or multi-principal auth
behavior in P0.

## Where the next gardeners begin

S1 begins with **SPEC C.2 plus ADR-004**: literal model mappings and the
transactional CAS/revision/tombstone rules. After S1, S2 begins with **SPEC
C.4 memory endpoints plus C.5**: memory CRUD and the two dedup bands. P0 has
not prebuilt either packet's behavior.

## Verification

On 2026-07-17, the frozen spec matched the workspace master byte for byte,
Ruff lint and format checks passed, and all 17 pytest checks passed against
Python 3.12.9 and disposable pgvector Postgres. Tests exercise the new index's
collision/reuse behavior, v1.5 request requirements and paging validation, all
seven inert routes, and committed OpenAPI drift.

A clean Compose build returned the authenticated health response. Alembic
reported `0001 (head)`, Postgres exposed the exact partial unique index, the
v0 seed remained intact, and live valid v1.5 calls to all seven C.4 routes
returned their named RFC 7807 `501` responses. The scope fence passed the
repository. Reproducible commands and output are in
`verification/bootstrap/README.md`.
