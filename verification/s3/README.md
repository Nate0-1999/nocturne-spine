# S3 scorer and inject/prepare evidence

This is packet evidence, not the independent M1 verdict reserved by SPEC B.6.
It records how to reproduce the C.3 scorer and C.4 prepare behavior delivered
under Garden A-007 and A-008.

## Commands

From the Spine repository root:

```sh
PYTHONPATH=src uv run python scripts/generate_openapi.py
uv run ruff check .
uv run ruff format --check .
uv lock --check
PYTHONPATH=src TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock uv run pytest -ra
.githooks/pre-commit --all
docker compose config --quiet
docker build -t n8-spine:s3-check .
```

`PYTHONPATH=src` is the existing macOS File Provider workaround. The Docker
socket override is the existing Colima requirement; neither changes product
behavior.

## Recorded result — 2026-07-19

Pytest used Python 3.12.9, started disposable `pgvector/pgvector:pg16`, applied
production migration `0001`, and completed:

```text
71 passed in 3.75s
```

Ruff lint/format, the uv lock check, M1 scope fence, Compose validation, and the
production image build all passed. The final image was tagged
`n8-spine:s3-check` (local image `a786b981c1d7`). Harness remained green at 27
passed with its one intentional H2 live-contract skip; its Ruff and scope checks
also passed.

## Independent golden calculation

`tests/test_inject_scorer.py` fixes the snapshot clock and constructs this card
without consulting production output:

```text
f_sem  = 0.6
f_kw   = 3 / 3 = 1.0
f_time = 2^(-14/14) = 0.5
f_proj = 1.0
f_freq = 5 / 10 = 0.5
f_hist = 2^(-7/7) = 0.5
bias   = 0.03

score = .42(.6) + .16(1) + .11(.5) + .16(1)
      + .08(.5) + .07(.5) + .03
      = .732
```

C.2 stores score as PostgreSQL `REAL`, so the scorer quantizes once before
thresholding, sorting, response, and persistence; the wire/event value for that
calculation is `0.7319999933242798`. The test compares it to the hand result
within the storage precision and separately proves exact event/response parity.

## What the checks prove

- all six features follow the enacted tokenizer, stopword, project, citation,
  decay, human-edit, semantic-clamp, bias, and snapshot-clock rules;
- raw pgvector cosine forms the stable top-50 pool before `f_sem` clamps
  negatives, then score/UUID ordering drives an inclusive tau, top-k, greedy
  body-token budget, continued scanning after an oversized card, and near
  misses from every unselected reason;
- pins remain principal/project/status scoped but sit outside the vector pool,
  threshold, top-k, and hard budget, appear first with full features, and reduce
  regular budget by their `cl100k_base` body cost;
- percentage budgets floor exactly even for arbitrarily large JSON integers,
  and score decisions use the same PostgreSQL `REAL` value the API and event log
  expose;
- prepare embeds once, stamps a database-clock snapshot, reads candidates under
  repeatable read, writes one event per returned card with the frozen `_memory`
  payload, and rejects another prepare for the M1 one-injection thread;
- a deliberately paused prepare excludes a post-snapshot create and returns the
  pre-edit body/vector of a concurrently changed near miss, while its event keeps
  that same frozen card after the live head advances;
- injected and pinned cards alone increment `stats.injections` and
  `last_injected_at` through the C.2 CAS/history helper; two concurrent threads
  selecting one memory finish at revision 3 with two events and no lost count;
- event score/features/rank exactly equal the response, shown-as membership is
  exact, event/card/stat writes share one rollback boundary, and the root-to-
  system revision carries `system:inject`, request machine, and prepare reason;
- project, principal, and active-status filters prevent leakage; thread identity
  must match before an unstamped row can be used; provider failure and request
  validation remain write-free RFC7807 responses;
- committed OpenAPI advertises live prepare success/409/503 shapes with no 501,
  while commit, feedback, and search remain their named S4/S2-follow-on stubs.
