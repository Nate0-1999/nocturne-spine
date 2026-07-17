# Agent Zero v1.5 refresh evidence

This directory records reproducible evidence for P0. It is not an M1 verdict;
SPEC B.6 reserves that judgment for an independent agent using the real UI.

## Commands

From the repository root:

```sh
cmp docs/SPEC.md ../garden_v1/harness-memory-spec.md
uv sync --extra dev
uv run python scripts/generate_openapi.py
uv run ruff check .
uv run ruff format --check .
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest
.githooks/pre-commit --all
SPINE_TOKEN=local-development-token docker compose up --build -d
curl -H 'Authorization: Bearer local-development-token' http://localhost:8000/healthz
docker compose exec postgres psql -U spine -d spine -c 'SELECT version_num FROM alembic_version;'
docker compose exec postgres psql -U spine -d spine -c "SELECT indexdef FROM pg_indexes WHERE indexname = 'memory_unit_active_label';"
docker compose exec postgres psql -U spine -d spine -c "SELECT version, weights, params, active FROM scorer_config;"
docker compose exec spine alembic current
docker compose down -v
```

The socket override is needed by this workstation's Colima context so Ryuk can
mount the daemon socket. CI and standard Docker environments run `pytest`
without it.

## Recorded result — 2026-07-17 v1.5 refresh

The frozen law check returned success: `docs/SPEC.md` is byte-for-byte equal
to `garden_v1/harness-memory-spec.md`. `AGENTS.md` and `CLAUDE.md` are equal to
each other and reproduce Garden Plan §6's v1.5 template.

Ruff:

```text
23 files already formatted
All checks passed!
```

The pytest run used Python 3.12.9, started disposable
`pgvector/pgvector:pg16`, applied migration 0001 through Alembic, and completed:

```text
17 passed in 3.47s
```

The added tests prove:

- `memory_unit_active_label` is unique only while a unit is active and permits
  replacement after quarantine;
- create and PATCH require v1.5 `machine_id`, create accepts `force`, and
  unknown request fields remain rejected;
- list accepts the exact `limit=200&offset=7` signature and rejects a limit
  above the specified maximum;
- committed OpenAPI contains the v1.5 success/conflict schemas and matches the
  app factory exactly, including concrete prepare scoring details versus
  required-null dedup/search `features` and `rank`.

The Compose cold start built the Python 3.12 image, waited for Postgres,
applied migration 0001, and started Uvicorn. The authenticated health response
was:

```json
{"ok":true,"version":"0.1.0"}
```

Database trace:

```text
alembic_version: 0001
alembic current: 0001 (head)
memory_unit_active_label: CREATE UNIQUE INDEX ... (principal_id, label)
                          WHERE (status = 'active'::text)
vector extension: installed
tables: memory_unit, memory_revision, thread, injection_event, scorer_config
scorer_config.version: v0
scorer_config.active: true
```

Live valid v1.5 requests exercised every C.4 stub through the container
boundary:

```text
POST /v1/inject/prepare -> 501 application/problem+json endpoint=POST /v1/inject/prepare
POST /v1/inject/commit -> 501 application/problem+json endpoint=POST /v1/inject/commit
POST /v1/feedback -> 501 application/problem+json endpoint=POST /v1/feedback
POST /v1/memories -> 501 application/problem+json endpoint=POST /v1/memories
PATCH /v1/memories/{id} -> 501 application/problem+json endpoint=PATCH /v1/memories/{id}
GET /v1/memories?limit=200&offset=7 -> 501 application/problem+json endpoint=GET /v1/memories
POST /v1/search -> 501 application/problem+json endpoint=POST /v1/search
```

Compose was then stopped and its disposable volume removed.

## M1 scope fence

The tracked `.githooks/pre-commit --all` check passed over the complete
repository. The original P0 isolated staged probe already demonstrates that
the hook rejects a forbidden online-weight update marker; this v1.5 refresh
does not change the fence.
