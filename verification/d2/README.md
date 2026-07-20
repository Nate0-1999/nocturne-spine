# D2 billing circuit-breaker evidence

This is packet evidence, not a live-cloud deployment record or the independent
M1 verdict reserved by SPEC B.6. D2's agent boundary ends at source, fixture
tests, local packaging checks, and a human-only runbook. No live notification,
billing detach, IAM change, Pub/Sub publish, function deployment, or recovery
command was performed.

## Commands

From the Spine repository root:

```sh
uv lock --check
uv run ruff check .
uv run ruff format --check .
.githooks/pre-commit --all
PYTHONPATH=src uv run python scripts/generate_openapi.py
git diff --exit-code -- openapi.json
docker compose config --quiet
if rg -n 'not_implemented|STUB_RESPONSES|501' src openapi.json; then exit 1; fi
bash -n infra/billing-breaker/deploy.sh
TESTCONTAINERS_RYUK_DISABLED=true PYTHONPATH=src uv run --extra dev pytest -ra
docker build -t n8-spine:d2-check .
git diff --check
```

The D2-only fixture and deployment-validator suite was also isolated with:

```sh
PYTHONPATH=src uv run --extra dev pytest -q tests/test_billing_breaker.py
```

The function adapter was imported with its two exact pinned dependencies and a
local fake client. The smoke check constructed the real
`google.cloud.billing_v1.ProjectBillingInfo`, asserted the fixed project plus
empty account request, accepted only the empty/disabled response, and made no
client construction or network call:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run \
  --with functions-framework==3.10.2 \
  --with google-cloud-billing==1.20.0 \
  python -  # local fake-client assertions supplied on stdin
```

From the Harness repository root:

```sh
uv lock --check
uv run ruff check .
uv run ruff format --check .
.githooks/pre-commit --all
PYTHONPATH=src uv run pytest -ra
npm run lint --prefix web
npm run build --prefix web
```

`PYTHONPATH=src` is the existing macOS File Provider workaround recorded by
earlier packets. Disabling the Testcontainers reaper avoids the existing Colima
socket-mount incompatibility; the disposable PostgreSQL container and product
behavior are unchanged.

## Recorded result — 2026-07-19

The final Spine suite used Python 3.12.9, started disposable
`pgvector/pgvector:pg16`, applied production migrations through `0002`, and
completed:

```text
158 passed in 5.05s
```

The isolated D2 suite completed `76 passed in 0.04s`. Ruff lint/format, uv lock,
M1 scope fence, Compose validation, committed OpenAPI freshness, zero-501
fence, shell syntax, diff whitespace, and the pinned runtime-adapter smoke test
all passed. The production Spine image was rebuilt as `n8-spine:d2-check` with
local image ID
`sha256:f8ef320f936ae2c847294fe018ea5a512bb0d5396e50ae68ed78c241889099ba`.

Harness completed:

```text
27 passed, 1 skipped in 0.17s
```

The skip is the intentional H2 live-contract reservation. Harness Ruff,
formatting, uv lock, scope fence, web lint, and production web build passed. An
initial unprefixed Harness pytest invocation failed collection because the
editable `src/` package was hidden by the known File Provider behavior; the
documented `PYTHONPATH=src` rerun above passed all tests.

No real `gcloud` command or cloud API call was made. During development, one
now-removed local unit test invoked `deploy.sh --dry-run` against a fake
`gcloud` sentinel. The script exited before lookup or mutation, but this still
crossed PLAN's literal “never execute the deploy script” agent boundary; it is
recorded here rather than represented as compliant. The apply mode and all live
deployment/recovery commands remained unexecuted.

## What the checks prove

- fixture notifications below, exactly at, and above the budget exercise the
  literal decimal comparison; equality and overage request the same fixed
  `projects/n8-memory-palace` empty-account state;
- duplicate delivery is desired-state idempotent, while malformed, foreign,
  wrong-schema, wrong-currency, and non-finite/invalid values are logged and
  acknowledged without constructing a Cloud Billing gateway;
- detach intent, success, and sanitized failure decisions are structured and
  API failures propagate with trigger retries explicitly disabled;
- the adapter sends the exact Cloud Billing request and rejects a response that
  does not confirm both disabled billing and an empty account assignment;
- deployment validators pin the existing billing-account-owned, recurring
  whole-project USD 100 budget, disconnected/armed phases, Python 3.12 Gen 2 function, entry point,
  environment IDs, three separated identities, Eventarc topic/region/type,
  root delivery route, no-retry policy, private service Invoker policy, exact
  budget publisher, one target-project subscription exactly matching the
  healthy function-owned Eventarc transport, empty subscription IAM, and no
  Pub/Sub message transforms;
- the human script is default-inert, interactive, first-deploy-only, and uses
  successful exact list results for absence; it wires the budget only after
  inert-topology validation and grants project-only detach authority last;
- every direct project and billing-account role is resolved to its current
  permissions; budget/resource-budget mutation, billing-account IAM or detach,
  project billing assignment, public access, credential overrides, and
  same-number identities outside a fixed Google service-agent domain set fail
  closed;
- cleanup intent is recorded before ambiguous IAM writes; error and termination
  traps revoke applicable detach/build roles and require a fresh policy read to
  prove absence, otherwise they emit a critical unresolved-authority warning;
- the runbook correlates its only permitted live drill to the returned Pub/Sub
  message ID and machine-checks that billing remains attached, while recovery
  rejects command errors as proof of absence, deletes every subscription found
  through the topic-side index independently of Eventarc state and subscription
  owner project, deletes or irreversibly detaches each, and verifies the trigger,
  service, function, topic, roles, queues, and service accounts before reattachment.

## Human gate still required

A human must audit inherited/custom IAM and trusted administrators, verify an
off-project backup and current-period actual cost below USD 100, identify the
exact existing budget and billing account, review `deploy.sh --dry-run`, and
then decide whether to run the interactive `--apply` gate. The safe live drill
and ordered recovery/reattach procedure remain human-only. D2 code being green
does not mean the breaker is deployed or that USD 100 is a real-time hard cap.
