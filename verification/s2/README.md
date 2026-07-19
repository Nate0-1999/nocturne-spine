# S2 memory CRUD and dedup evidence

This is packet evidence, not the independent M1 verdict reserved by SPEC B.6.
It records how to reproduce the C.4 create, PATCH, list, embedding-provider,
and concurrency checks delivered by S2 under Garden A-002 through A-006.

## Commands

From the Spine repository root:

```sh
uv sync --extra dev
PYTHONPATH=src uv run python scripts/generate_openapi.py
uv run ruff check .
uv run ruff format --check .
PYTHONPATH=src TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest -ra
.githooks/pre-commit --all
docker compose config --quiet
docker build -t n8-spine:s2-check .
```

`PYTHONPATH=src` is the existing macOS File Provider workaround recorded by
S1; it changes no source or dependency behavior. The Docker socket override is
the existing Colima requirement recorded by P0.

## Recorded result — 2026-07-19

Ruff lint/format, the M1 scope fence, Compose configuration, the production
image build, and the uv lock check passed. Pytest used Python 3.12.9, started disposable
`pgvector/pgvector:pg16`, applied production migration `0001`, and completed:

```text
52 passed
```

The S2 checks prove:

- create checks active-label ownership before provider I/O, validates the
  enacted 64-character/128-`cl100k_base` limits, embeds the body, and writes one
  atomic head plus attributed root revision with a canonical ULID;
- hard duplicates at `score >= 0.92` return the exact 409 card even with
  `force=true`; the similar band is `0.80 <= score < 0.92`, returns every card
  in score/UUID order, writes nothing, and only that band can be forced;
- simultaneous identical-vector creates for one principal serialize inside
  PostgreSQL and produce one 201, one exact 409, and one persisted root;
- provider output is checked for cardinality, index order, finite numeric
  values, non-zero norm, and exactly 1536 dimensions before storage; the real
  runtime adapter uses OpenAI's embeddings endpoint while tests inject vectors;
- PATCH re-embeds body replacements and atomically advances head/history through
  the S1 CAS path; stale, label, activation, absent-ID, null/no-op, and limit
  paths preserve the enacted precedence, media type, and rollback semantics;
- list filters compose, `q` is trimmed and literal/case-insensitive over
  label/body, filtered totals precede paging, and equal timestamps/UUIDs retain
  the exact stable order with enforced paging minima/maxima;
- the committed OpenAPI artifact has no 501 on implemented routes, advertises
  exact JSON domain conflicts and RFC7807 generic errors, and matches the app;
- unexpected service failures are sanitized RFC7807 500 responses, while an
  unavailable or invalid embedding provider is an RFC7807 503 with no write.

The untouched inject/prepare, inject/commit, feedback, and search endpoints
remain named 501 stubs for S3/S4. Harness's inherited suite also remained green:
27 passed with the one intentional H2 live-contract skip.
