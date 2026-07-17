# Agent Zero bootstrap evidence

This directory records reproducible evidence for P0. It is not an M1 verdict;
SPEC B.6 reserves that judgment for an independent agent using the real UI.

## Commands

From the repository root:

```sh
uv sync --extra dev
uv run ruff check .
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest
SPINE_TOKEN=local-development-token docker compose up --build -d
curl -H 'Authorization: Bearer local-development-token' http://localhost:8000/healthz
docker compose exec postgres psql -U spine -d spine -c 'SELECT version_num FROM alembic_version;'
docker compose exec postgres psql -U spine -d spine -c "SELECT version, weights, params, active FROM scorer_config;"
docker compose exec spine alembic current
docker compose down -v
```

The socket override is needed by this workstation's Colima context so Ryuk can
mount the daemon socket. CI and standard Docker environments run `pytest`
without it.

## Recorded result — 2026-07-17

`uv run ruff check .`:

```text
All checks passed!
```

The pytest run used Python 3.12.9, started a disposable
`pgvector/pgvector:pg16` container, applied migration 0001 through Alembic,
and completed:

```text
collected 14 items
tests/test_api.py .............                                         [ 92%]
tests/test_migration.py .                                               [100%]
14 passed
```

The Compose cold start built the Python 3.12 image, waited for Postgres to be
healthy, applied migration 0001, and started Uvicorn. The authenticated health
response was:

```json
{"ok":true,"version":"0.1.0"}
```

Database trace:

```text
alembic_version: 0001
alembic current: 0001 (head)
vector extension: installed
tables: memory_unit, memory_revision, thread, injection_event, scorer_config
column counts: memory_unit=17, memory_revision=10, thread=7,
               injection_event=19, scorer_config=5
indexes: C.2 HNSW, principal/status/project, revision lineage, and injection id
constraints: C.2 primary/foreign/unique keys plus kind/status/shown_as checks
scorer_config.version: v0
scorer_config.weights: {"kw": 0.16, "sem": 0.42, "freq": 0.08, "hist": 0.07, "proj": 0.16, "time": 0.11}
scorer_config.params: {"tau": 0.55, "top_k": 8, "budget_pct": 0.05, "near_miss_k": 3, "budget_tokens": 3000, "candidate_pool": 50, "never_bias_step": -0.15, "quarantine_kills": 3, "half_life_hist_days": 7, "half_life_time_days": 14}
scorer_config.active: true
```

Live requests exercised every C.4 stub through the container boundary:

```text
POST /v1/inject/prepare -> 501 application/problem+json endpoint=POST /v1/inject/prepare
POST /v1/inject/commit -> 501 application/problem+json endpoint=POST /v1/inject/commit
POST /v1/feedback -> 501 application/problem+json endpoint=POST /v1/feedback
POST /v1/memories -> 501 application/problem+json endpoint=POST /v1/memories
PATCH /v1/memories/{id} -> 501 application/problem+json endpoint=PATCH /v1/memories/{id}
GET /v1/memories -> 501 application/problem+json endpoint=GET /v1/memories
POST /v1/search -> 501 application/problem+json endpoint=POST /v1/search
GET /healthz without bearer -> 401 application/problem+json
```

Compose was then stopped and its disposable volume removed.

## M1 scope fence

The tracked `.githooks/pre-commit --all` check passed over the complete
repository. An isolated staged probe containing a forbidden online-weight
update marker was then rejected with the SPEC B.4 stop message; the probe was
removed from the index immediately afterward.
