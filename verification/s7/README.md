# S7 broker-routed embedding evidence

This is packet evidence, not the independent M1 verdict reserved by SPEC B.6.
It records how to reproduce the C.1/C.5 v2.3 routing change delivered by S7.

## Commands

From the Spine repository root:

```sh
PYTHONPATH=src uv run python scripts/generate_openapi.py
uv run ruff check .
uv run ruff format --check .
uv lock --check
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock \
  PYTHONPATH=src uv run --extra dev pytest -q
.githooks/pre-commit --all
docker compose config --quiet
git diff --check
```

The Compose routing matrix was also rendered with non-secret sentinels for:

```text
default URL/model + OPENROUTER_API_KEY
explicit SPINE_OPENAI_API_KEY over broker and legacy keys
direct URL/model + explicit compatible key
```

From the sibling Harness repository:

```sh
PYTHONPATH=src uv run pytest -q -m 'not contract'
uv run ruff check .
uv run ruff format --check src tests
uv lock --check
.githooks/pre-commit --all
npm run lint --prefix web
npm run build --prefix web
sh tests/contract/run.sh
```

## Recorded result — 2026-07-20

- Spine: 160 tests passed in 5.48 seconds.
- Harness: 220 non-contract tests passed; 2 live tests were deselected.
- The disposable migrated production Spine image passed both live Harness
  contract tests and tore down cleanly.
- Ruff lint/format, both lock checks, both M1 scope fences, Compose validation,
  web lint/build, and diff checks passed.
- Regenerating `openapi.json` produced no change, and the committed-freshness
  assertion passed.

## What the checks prove

- runtime defaults route embeddings to `https://openrouter.ai/api/v1` with
  model `openai/text-embedding-3-small`;
- `SPINE_EMBED_BASE_URL` and `SPINE_EMBED_MODEL` reach the existing adapter, so
  a direct OpenAI-compatible endpoint can override both broker-specific values;
- the existing generic bearer slot accepts an explicit compatible key, while
  local Compose falls back through OpenRouter and then the legacy OpenAI input;
- both default and direct-provider composition paths are exercised through a
  deterministic, network-free provider constructor fake;
- provider response validation and the fixed `vector(1536)` boundary remain
  unchanged and retain their existing adapter and database coverage;
- S7 changes runtime composition only: the HTTP wire contract remains fresh,
  and Harness needs no mirrored model or client change.
