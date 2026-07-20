# S5 origin_path metadata evidence

This is packet evidence, not the independent M1 verdict reserved by SPEC B.6.
It records how to reproduce the C.2/C.4 `origin_path` behavior delivered by S5.

## Commands

From the Spine repository root:

```sh
PYTHONPATH=src uv run python scripts/generate_openapi.py
uv run ruff check .
uv run ruff format --check .
uv lock --check
TESTCONTAINERS_RYUK_DISABLED=true PYTHONPATH=src uv run --extra dev pytest -ra
.githooks/pre-commit --all
docker compose config --quiet
docker build -t n8-spine:s5-check .
```

`PYTHONPATH=src` is the existing macOS File Provider workaround. Disabling the
Testcontainers reaper avoids a local Colima socket-mount incompatibility; the
disposable Postgres container and product behavior are unchanged.

## Recorded result — 2026-07-19

Pytest used Python 3.12.9, started disposable `pgvector/pgvector:pg16`, applied
production migrations through `0002`, and completed:

```text
72 passed in 3.80s
```

Ruff lint/format, the uv lock check, M1 scope fence, Compose validation, and
the production image build all passed. The final image was tagged
`n8-spine:s5-check` (local image `01470e1e5f50`). Harness remained green at 27
passed with its one intentional H2 live-contract skip; its Ruff lint/format,
uv lock, and scope fence also passed.

## What the checks prove

- migration `0002` adds exactly nullable, default-free `origin_path TEXT`, and
  ORM metadata matches the migrated schema without rewriting migration `0001`;
- create preserves a supplied workspace-relative string literally, omission
  returns explicit null, and the shared required-but-nullable `MemoryUnit`
  shape carries the field through create, list, and stale-CAS responses;
- a path-only PATCH advances head/history through the existing CAS writer and
  performs no embedding call; an unrelated later CAS retains the metadata;
- under enacted Garden A-004, `origin_path: null` remains omitted: null alone
  is a 422 no-op and null beside another mutation preserves the current path;
- committed OpenAPI makes `origin_path` optional and nullable on create/PATCH,
  required and nullable on `MemoryUnit`, and absent from scoring features;
- the unchanged S3 scorer and inject suites retain exactly six features,
  scorer-config v0 retains its original six weights, and frozen event `_memory`
  remains `{label, body, pin, updated_at}`—no location signal or null penalty
  was introduced in M1.
