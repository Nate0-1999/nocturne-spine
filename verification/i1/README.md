# I1 replay-integrity evidence

Status: **REPLAY PORTION COMPLETE; I1 OVERALL RETURNED TODO**

This is the completed Spine replay portion of the partial 2026-07-30 I1
handoff, not the independent M1 judge verdict. The Harness handoff lists the
remaining browser/SOP evidence work.

The integration gap fixed here is covered by:

```sh
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock \
TESTCONTAINERS_RYUK_DISABLED=true \
PYTHONPATH=src \
uv run --locked pytest -q \
  tests/test_inject_api.py::test_prepare_commit_replays_gate_and_prepare_updates_only_injected
```

The test drives a real prepare → commit sequence, then reads the persisted
PostgreSQL rows to prove:

- one prompt and scorer version reconstruct the gate;
- each card retains its frozen `_memory` snapshot and feature vector;
- `removed:not_relevant` and `added_back` outcomes replay exactly, with the
  removed body excluded and added-back body included in the committed block;
- prepare-time injection bookkeeping CAS-updates the injected unit without
  mutating the near-miss head.

The companion Harness evidence contains the live screenshots, replay SQL,
captured local-Compose rows, and exact canonical injection IDs:

- `../harness/verification/i1/README.md` from the Spine repository root;
- `../harness/verification/i1/replay.sql`;
- `../harness/verification/i1/2026-07-30/database-replay.json` (complete);
- `../harness/verification/i1/2026-07-30/database-replay.txt` (summary).

The local receipt proves the same canonical gate's prompt, `v0` scorer,
feature snapshots, scores, and outcomes. It also proves a later panel edit
changes the current head without changing the frozen event body. PostgreSQL
does not store rendered `final_block` as a separate column; the integrated
test proves removed/add-back membership from the frozen persisted inputs.
