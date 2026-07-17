# Spine Agent Zero bootstrap report

Status: **P0 scaffold complete; Garden packet blocked on FLAGS F001–F005**

## What exists

- A standalone Python 3.12 git repository with the exact C.1 package areas,
  the frozen byte-for-byte SPEC v1.4 reference at `docs/SPEC.md`, and both
  relay ground-rule files from Garden Plan §6.
- FastAPI app factory, static bearer middleware, RFC 7807 auth/validation/HTTP
  errors, and authenticated `/healthz` returning `{ok, version}`.
- Async SQLAlchemy/Alembic plumbing and migration `0001`, containing the full
  authoritative C.2 DDL plus active scorer `v0` seeded with C.3 weights and
  parameters.
- A Python 3.12 image and Compose topology with `pgvector/pgvector:pg16` plus
  `spine`; the service applies Alembic before Uvicorn starts.
- Ruff/pytest CI and testcontainers verification for migration, scorer seed,
  health/auth, validation, every stub, and committed OpenAPI drift.
- A tracked pre-commit scope fence, repeated over all tracked files in CI,
  which blocks the forbidden M1 feature families named by Garden Plan §7.

## What is deliberately stubbed

The complete C.4 M1 surface is registered but contains no business logic.
Each valid call returns `501 application/problem+json`, with an RFC 7807 body
whose `endpoint` extension names the stub:

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

## Literal contract seams left untouched

- C.2's `label` comment describes a principal-scoped partial unique index for
  active rows, but the authoritative SQL does not define one. Migration 0001
  does not invent it.
- C.4's memory-create behavior mentions retrying with `force=true`, but the
  exact request body and route signature do not define `force`. The P0 schema
  does not invent it.
- C.4 calls the memory list paged without defining paging parameters or a
  response body. Its create and patch bodies also omit the
  `origin_machine_id` that C.2 requires on every revision row. P0 does not add
  undocumented request fields or persistence defaults.

These and two related response-shape seams are recorded as Garden FLAGS
F001–F005 rather than silently resolved. The human must resolve them before
the relay advances.

## Where the next gardeners begin

S1 begins with **SPEC C.2 plus ADR-004**: literal model mappings and the
transactional CAS/revision/tombstone rules. After S1, S2 begins with **SPEC
C.4 memory endpoints plus C.5**: memory CRUD and the two dedup bands. P0 has
not prebuilt either packet's behavior.

## Verification

On 2026-07-17, Ruff passed, all 14 pytest checks passed against Python 3.12.9
and disposable pgvector Postgres, and a clean Compose build returned the
authenticated health response. Alembic reported `0001 (head)`, the v0 seed
matched C.3, and live calls to all seven C.4 stubs returned their named RFC
7807 responses. The scope fence passed the repository and rejected a staged
forbidden-feature probe. Exact commands and observed output are in
`verification/bootstrap/README.md`.
