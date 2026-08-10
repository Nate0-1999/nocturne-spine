# M2F — Chrysopoeia learner v1 evidence

Packet: `M2F`

Contract: Garden `A-031`

Decision: Spine `025` `[P1.2]`

## Delivered boundary

- `POST /retrain` runs one repeatable-read, advisory-lock-serialized batch over
  the hygiene-filtered `injection_event` log.
- Whole gates are split chronologically; the newest configured fraction is
  held out.
- Training constructs positive/negative pairs within each training gate and
  refits all six global weights under non-negative, sum-one constraints, plus
  L2-shrunk per-memory offsets.
- Replay grades binary injected/not-injected decisions. Explicit feedback on a
  passive-origin event remains a full-weight human signal; only passive keeps
  and autonomous entries receive the configured discount.
- A winner is inserted as one inactive, content-addressed `scorer_config` row.
  Repeating the same fit returns the same version and does not duplicate it.
- The proposal copies manual tau, budget, k, decay, and pool parameters
  unchanged. Retraining never activates a version or mutates online head bias.
- `SPINE_RETRAIN_SIGNAL_STRIDE` defaults to 25. One startup/work-woken worker
  asks the same advisory-locked service whether the canonical disposition count
  has reached the floor or next stride; no request waits for a fit.
- Every actual fit appends an immutable `learner_run` receipt. Background work
  can only persist an inactive proposal; activation remains an explicit owner act.

## Deterministic acceptance map

| Requirement | Evidence |
|---|---|
| exact whole-log pairwise re-fit | `tests/test_learner_model.py::test_whole_log_fit_is_deterministic_simplex_constrained_and_shrunk` |
| newest-gate time split | `tests/test_learner_model.py::test_time_split_keeps_whole_gates_and_uses_newest_for_holdout` |
| binary override referee + passive discount | `tests/test_learner_model.py::test_binary_replay_counts_each_override_and_applies_passive_discount` |
| real margin + cheaper-at-tie | `tests/test_learner_model.py::test_replay_winner_requires_margin_except_for_exact_cheaper_tie` |
| test/fixture/verification hygiene | `tests/test_learner_api.py::test_retrain_hygiene_excludes_whole_verification_gate` |
| inactive proposal + reproducible idempotence | `tests/test_learner_api.py::test_retrain_proposes_inactive_content_addressed_winner_idempotently` |
| later activation applies learned offsets | `tests/test_inject_scorer.py::test_active_learner_version_adds_immutable_offset_to_online_head_bias` |
| authenticated bodyless trigger | `tests/test_api.py::test_retrain_is_bearer_protected_before_any_training_work` and committed `openapi.json` |
| work wake uses same service | `tests/test_learner_worker.py::test_worker_checks_startup_work_and_subsequent_wakes_then_stops` |
| durable floor/stride receipts | `tests/test_learner_api.py::test_manual_retrain_below_floor_does_not_delay_floor_and_above_floor_resets_stride` |
| fresh serialized due checks | `tests/test_learner_api.py::test_manual_receipt_makes_waiting_background_fresh_noop` and `tests/test_learner_api.py::test_competing_backgrounds_at_one_boundary_fit_once` |
| learner-lock cleanup after failure | `tests/test_learner_api.py::test_learner_lock_is_released_after_snapshot_failure` |
| real background winner remains inactive | `tests/test_learner_api.py::test_real_worker_startup_and_work_wake_persists_background_inactive_winner` |
| forced manual basin yields visible learner proposal | `tests/test_learner_api.py::test_force_values_basin_yields_visible_measured_inactive_learner_proposal` |
| server-authored learning view | `tests/test_m2k_api.py::test_console_learning_view_is_one_exact_server_authored_scoreboard` |

## Verification commands

```bash
TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock \
TESTCONTAINERS_RYUK_DISABLED=true \
PYTHONPATH=src uv run --locked pytest -q

uv run --locked ruff check src tests
```

This packet has no user-facing surface and makes no provider call, so browser
or model-response theater would add no evidence. Its acceptance boundary is the
stored log, exact numeric replay, database proposal row, and unchanged active
scorer.
