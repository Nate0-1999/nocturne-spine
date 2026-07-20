# S4 commit, feedback, and quarantine evidence

This is packet evidence, not the independent M1 verdict reserved by SPEC B.6.
It records how to reproduce the C.3/C.4/C.6 behavior delivered under Garden
A-009 through A-011.

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
docker build -t n8-spine:s4-check .
```

`PYTHONPATH=src` is the existing macOS File Provider workaround. Disabling the
Testcontainers reaper avoids a local Colima socket-mount incompatibility; the
disposable Postgres container and product behavior are unchanged.

## Recorded result — 2026-07-19

Pytest used Python 3.12.9, started disposable `pgvector/pgvector:pg16`, applied
production migrations through `0002`, and completed:

```text
79 passed in 4.81s
```

Ruff lint/format, the uv lock check, M1 scope fence, Compose validation,
committed OpenAPI freshness, and the production image build all passed. The
final image was tagged `n8-spine:s4-check` (local image
`3dda7c33e339967332ed47a663c3f99996cb73170ebc214021d6330330f47fe6`). Harness
remained green at 27 passed with its one intentional H2 live-contract skip;
its Ruff lint/format, uv lock, and scope fence also passed.

## What the checks prove

- commit validates the complete event batch before writing, rejects duplicate,
  foreign, cross-class, overlapping, and conflicting choices with RFC7807, and
  treats same-outcome and feedback-descendant retries idempotently;
- injected and pinned members become kept or removed, selected near misses
  become added back, untouched near misses stay null, and eventless or
  all-near-miss empty decisions return the one canonical empty block;
- every newly removed or added-back event updates the current head exactly once
  through C.2 CAS/history, with UUID-ordered locks, exact editor/machine/reason
  attribution, outer-transaction rollback, and no lost counts under forced
  concurrent requests;
- add-back uses a post-lock database clock, so two different injection IDs
  writing one memory cannot regress `last_injected_at` even when their initial
  clock order opposes their serialized head-write order;
- never decisions load bias and quarantine thresholds from the event's historic
  scorer version, quarantine an active head at that version's threshold, and
  preserve already tombstoned status;
- wrong removals return the post-stat current MemoryUnit (including
  `origin_path`) in event-rank order while final members render only from the
  frozen S3 event card, not the current head;
- final blocks have exact rank/UUID order, attribute order, LF structure,
  zero-member form, attribute control-character/entity escaping, body escaping,
  preserved body whitespace, and no terminal newline;
- feedback targets exact event membership, accepts only kept/added-back sources,
  serializes identical concurrent retries, rejects conflicting states, and
  rolls back its head CAS if the event transition fails;
- mid-thread removal increments only removals with exact lineage attribution;
  cited remains event-log-only with no statistic, revision, or scorer-v0 effect;
- generated OpenAPI advertises live commit/feedback success and problem shapes
  with no 501; the only remaining named contract stub is `/v1/search`.
