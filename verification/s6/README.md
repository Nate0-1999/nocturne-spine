# S6 semantic search evidence

This is packet evidence, not the independent M1 verdict reserved by SPEC B.6.
It records how to reproduce the C.3/C.4 `/v1/search` behavior delivered under
Garden A-012.

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
if rg -n 'not_implemented|STUB_RESPONSES|501' src openapi.json; then exit 1; fi
docker build -t n8-spine:s6-check .
```

`PYTHONPATH=src` is the existing macOS File Provider workaround. Disabling the
Testcontainers reaper avoids a local Colima socket-mount incompatibility; the
disposable Postgres container and product behavior are unchanged.

## Recorded result — 2026-07-19

Pytest used Python 3.12.9, started disposable `pgvector/pgvector:pg16`, applied
production migrations through `0002`, and completed:

```text
82 passed in 5.00s
```

Ruff lint/format, the uv lock check, M1 scope fence, Compose validation,
committed OpenAPI freshness, the zero-501 fence, and the production image build
all passed. The final image was tagged `n8-spine:s6-check` (local image
`365f48994cbfcd242feb903db76591c409dfb33a8c586c598645c9183f8ffc06`). Harness
remained green at 27 passed with its one intentional H2 live-contract skip;
its Ruff lint/format, uv lock, and scope fence also passed.

## What the checks prove

- search embeds exactly once through the validated production provider boundary
  and returns current ACTIVE heads for the exact principal;
- omitted and JSON-null project context search every project for that principal,
  while a non-null context admits global plus exact-project units only;
- results use raw cosine similarity with no threshold, clamp, scorer weights,
  bias, or pin priority; a negative-similarity unit with large positive bias is
  still returned in raw-cosine order;
- distance ties break by memory UUID, the default returns exactly ten, and both
  enacted boundaries (`k=1` and `k=50`) are accepted;
- zero, oversized, and boolean `k` values return RFC7807 422 before provider
  work, while invalid provider vectors return the exact 503 problem response;
- every result is the shared eight-field SimilarityMemoryCard with raw `score`,
  current label/body/kind/pin, and required `features:null` / `rank:null`;
- an empty candidate set returns `200 {"results":[]}`;
- generated OpenAPI freezes the default/minimum/maximum and 503 response, and no
  501/stub marker remains anywhere in Spine source or the committed contract.
