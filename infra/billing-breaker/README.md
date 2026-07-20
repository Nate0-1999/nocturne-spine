# D2 billing circuit breaker

This package is an armed, one-way cost control for `n8-memory-palace`. A valid
budget message with `costAmount >= budgetAmount` calls Cloud Billing
`updateBillingInfo` with an empty `billingAccountName`. That deliberately
detaches the project's billing account and can stop or irretrievably delete
Cloud Run, Cloud SQL, and every other billable project service. There is no
simulation switch in the deployed function.

Agents may build and test this directory. **Only a human may run `deploy.sh
--apply`, publish a live message, alter IAM, or execute recovery commands.**

## What this does

- accepts only Pub/Sub schema `1.0` messages whose `billingAccountId` and
  `budgetId` match deploy-time settings;
- keeps the destructive target fixed in source as `projects/n8-memory-palace`;
- compares JSON numbers as decimals and detaches at equality or overage;
- emits one-line structured JSON decisions before and after the action;
- acknowledges malformed, foreign, and below-budget messages without creating
  a Cloud Billing client;
- surfaces Cloud Billing failures, while the deployed trigger explicitly does
  not retry failed events; the next periodic budget status is the next attempt;
- makes duplicate delivery state-idempotent by repeatedly requesting the same
  empty billing-account assignment, without a broader status-read permission.

Google documents the [budget notification schema, periodic delivery, and
at-least-once semantics](https://docs.cloud.google.com/billing/docs/how-to/budgets-programmatic-notifications),
the [empty-account detach operation](https://docs.cloud.google.com/billing/docs/reference/rest/v1/projects/updateBillingInfo),
the [disable-billing pattern and blast radius](https://docs.cloud.google.com/billing/docs/how-to/disable-billing-with-notifications),
and the [function retry hazard](https://docs.cloud.google.com/run/docs/tips/function-retries).
Retries are disabled because a permanent IAM/configuration failure could
otherwise keep an old over-budget event alive and detach again after recovery.

This is not a hard or real-time $100 cap. Budget data is estimated and delayed,
notifications arrive only several times per day, delivery can be duplicated or
out of order, and already-incurred but unreported charges remain payable.

## Human preflight

Stop if any item is uncertain:

1. Put the Cloud SQL backup and D1 redeploy material **outside
   `n8-memory-palace`**. A backup in the project can become unavailable with the
   project it is meant to restore. Google warns that disabling billing can
   remove resources and recovery is not guaranteed.
2. In Cloud Billing Reports, verify the current-period **actual** cost is below
   USD 100 immediately before arming. If it is already at or over USD 100,
   connecting the budget is an intentional near-term outage.
3. Confirm the existing budget has `ownershipScope: BILLING_ACCOUNT`, is
   recurring monthly, specified USD 100.00, filtered to only the numeric project
   resource for `n8-memory-palace`, and has no service, label, subaccount,
   resource-ancestor, custom-period, or credit filter. Its Pub/Sub notification
   topic must be disconnected.
4. Confirm the project-to-billing-account link is unlocked and the account has
   no active or pending commitment that prevents detachment.
5. Audit inherited/custom access on both the project and the named billing
   account for `billing.budgets.update`, `billing.resourcebudgets.write`,
   `billing.accounts.setIamPolicy`, Pub/Sub topic/subscription update or IAM,
   Eventarc trigger update or IAM, topic subscription attachment/detachment,
   `pubsub.topics.publish`, `run.routes.invoke`, billing association changes,
   `iam.serviceAccounts.actAs`, token/key minting, and IAM-policy mutation.
   Pub/Sub attributes are not signatures, and a principal that can retarget or
   lower the exact budget can make Google's publisher emit an authentic outage
   event. The budget must use `ownershipScope: BILLING_ACCOUNT`, making project
   principals read-only even when they otherwise have resource-budget write
   permission. For every direct project and billing-account binding, the script
   reads
   the role's current `includedPermissions`; only the active human may directly
   control the budget or billing-account IAM. It rejects other dangerous project
   permissions except the exact armed runtime binding and project-number-pinned
   identities at a fixed allowlist of Google-owned service-agent domains. It
   separately requires
   empty direct policies and no user-managed keys on all fresh D2 identities,
   only Google's budget publisher on the topic, and only the trigger identity
   on the service. The armed path must have one target-project Eventarc
   subscription that exactly equals the function-owned Eventarc trigger's
   output-only transport, a healthy exact destination, no direct subscription
   policy, and no topic or subscription Single Message Transforms because those
   can rewrite both payload data and attributes. Inherited roles, group
   membership, and humans who can command
   a trusted service agent are not fully resolved by those direct policies and
   remain a manual destructive-admin boundary.
6. Use a human identity, not service-account credentials. Remove all effective
   gcloud impersonation, access-token-file, and credential-file overrides; the
   script refuses them before trusting `gcloud auth list`. The simplest
   auditable gate is the sole direct Project Owner on `n8-memory-palace` plus
   Billing Account Administrator on the named account. Any other direct
   principal with a dangerous current permission makes the script stop. The
   named `roles/billing.projectManager` binding must be absent before arming;
   D2 reserves that exact role for its runtime identity. Recovery still needs
   the permissions documented by Google: Project Billing Manager + Browser +
   Service Usage Viewer on the project and Billing Account User + Viewer on the
   account, obtained only after the breaker is torn down if Owner is not used.

The [billing-link permissions](https://docs.cloud.google.com/billing/docs/how-to/modify-project#required_permissions)
matter during recovery: Billing Account Costs Manager alone cannot reattach a
project.

Identify the exact existing budget; never select it by display name:

```sh
export BILLING_ACCOUNT_ID=000000-000000-000000
gcloud billing budgets list --billing-account="${BILLING_ACCOUNT_ID}"
export BUDGET_RESOURCE="billingAccounts/${BILLING_ACCOUNT_ID}/budgets/BUDGET_ID"
gcloud billing budgets describe "${BUDGET_RESOURCE}"
```

## Review, then deploy

The dry run is local-only: it validates its two arguments and prints the plan
without looking for or invoking `gcloud`.

```sh
cd infra/billing-breaker
export BILLING_ACCOUNT_ID=000000-000000-000000
export BUDGET_RESOURCE="billingAccounts/${BILLING_ACCOUNT_ID}/budgets/BUDGET_ID"
./deploy.sh --dry-run
```

`--apply` is deliberately first-deploy-only. The function, Cloud Run service,
topic, every Eventarc trigger that references a D2 name, and all three service
accounts must be absent. A failed deployment or a rearm must go through the
cleanup procedure instead of silently adopting unknown identities, keys,
triggers, or queued messages.

After reviewing the plan and completing the preflight, a human can enter the
interactive gate:

```sh
export CONFIRM_D2_PROJECT=n8-memory-palace
./deploy.sh --apply
```

The script repeats the project, budget, account, destructive action, and
below-USD-100 assertion in a typed confirmation before its first mutation. It
rejects ambient credential overrides, resolves every direct role to its current
permissions, and uses successful list responses for its fresh-resource checks,
rather than treating any failed `describe` as absence. It then:

1. validates the enabled billing link and exact disconnected budget;
2. creates a fresh `billing-breaker` topic;
3. separates the runtime, Eventarc trigger, and build identities;
4. gives the build identity only Google's documented build roles and removes
   all three immediately when the build completes;
5. deploys a private Python 3.12 second-generation function with retries off;
6. gives the trigger identity Invoker only on this Cloud Run service and gives
   only Google's budget publisher direct topic Publisher access;
7. validates the complete inert topology;
8. requires the named Project Billing Manager role to be absent, then gives its
   sole unconditional membership to the runtime identity on this project
   immediately before connecting the budget last; and
9. asserts the complete armed state. Any later error enters a rollback that
   revokes applicable runtime/build roles and reads the project policy back.
   If absence cannot be proved, the script exits with a `CRITICAL` warning and
   the operator must assume detach authority remains active.

The runtime receives no billing-account, Artifact Registry, build, Eventarc,
or project-wide Invoker role. The trigger cannot detach billing, and the build
identity has no standing project role after deployment. Google documents the
[custom build identity roles](https://docs.cloud.google.com/functions/docs/building#secure_your_build_with_a_custom_service_account).

## Synthetic-message drill

The live drill is intentionally below budget. Equality and overage are proven
with fake-client unit tests; publishing either value to the armed topic would
perform the outage this breaker exists to cause. Do not add a new Publisher
binding merely to run the drill; use an already-trusted Project Owner or skip
the live drill.

```sh
export BUDGET_ID="${BUDGET_RESOURCE##*/}"
if ! drill_message_id="$(
  gcloud pubsub topics publish billing-breaker \
    --project=n8-memory-palace \
    --attribute="billingAccountId=${BILLING_ACCOUNT_ID},budgetId=${BUDGET_ID},schemaVersion=1.0" \
    --message='{"budgetDisplayName":"D2 safe drill","costAmount":99.99,"costIntervalStart":"2026-07-01T00:00:00Z","budgetAmount":100.00,"budgetAmountType":"SPECIFIED_AMOUNT","currencyCode":"USD"}' \
    --format='value(messageIds)'
)"; then
  echo "publish failed; drill did not pass" >&2
  exit 1
fi
if [[ -z "${drill_message_id}" || "${drill_message_id}" == *$'\n'* ]]; then
  echo "publish did not return exactly one message ID" >&2
  exit 1
fi
log_filter="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"billing-breaker\" AND jsonPayload.component=\"billing-breaker\" AND jsonPayload.action=\"below_budget\" AND jsonPayload.message_id=\"${drill_message_id}\""
if ! drill_log="$(
  gcloud logging read "${log_filter}" \
    --project=n8-memory-palace --limit=1 --format=json
)"; then
  echo "log lookup failed; drill did not pass" >&2
  exit 1
fi
DRILL_LOG="${drill_log}" python3 - <<'PY'
import json
import os

if not json.loads(os.environ["DRILL_LOG"]):
    raise SystemExit("no below_budget decision matched the published message ID")
PY
if ! billing_json="$(
  gcloud billing projects describe n8-memory-palace --format=json
)"; then
  echo "billing lookup failed; drill did not pass" >&2
  exit 1
fi
if ! printf '%s' "${billing_json}" | python3 deployment_checks.py billing \
  --billing-account-id "${BILLING_ACCOUNT_ID}"; then
  echo "billing validator failed; drill did not pass" >&2
  exit 1
fi
```

Pass means the exact published message ID has a `below_budget` JSON decision
and the machine-checked billing link remains enabled on the expected account.
Eventarc can take up to two minutes to propagate; an empty log result is a
failed/incomplete drill, so wait and repeat only the log and billing checks.
Do not republish merely because the log is delayed. Do not publish a message at
or above 100 to the live topic as a routine test. At-least-once delivery can
duplicate even a successful publish.

## Recovery and billing reattach

The order is a safety invariant. Do not restore the runtime role while an old
trigger, subscription, or topic exists, and do not reattach billing until the
breaker has neither authority nor a queue.

Set the exact resources first and run every block in the same Bash session.
Every absence proof below comes from a successful list request plus the same
exact-value validator used by deployment. Every validator is explicitly
guarded; permission, network, and parsing errors stop recovery.

```sh
: "${BUDGET_RESOURCE:?set the exact existing budget resource}"
: "${BILLING_ACCOUNT_ID:?set the billing account ID}"
```

1. In Cloud Billing **Budgets & alerts**, edit `BUDGET_RESOURCE`, disconnect
   its Pub/Sub topic, save, and machine-check that the field is empty:

   ```sh
   if ! budget_topic="$(
     gcloud billing budgets describe "${BUDGET_RESOURCE}" \
       --format='value(notificationsRule.pubsubTopic)'
   )"; then
     echo "budget lookup failed; disconnection is not proved" >&2
     exit 1
   fi
   if [[ -n "${budget_topic}" ]]; then
     printf 'budget is still connected to %s\n' "${budget_topic}" >&2
     exit 1
   fi
   ```

2. Revoke detach authority and verify the named role is completely absent:

   ```sh
   gcloud projects remove-iam-policy-binding n8-memory-palace \
     --member="serviceAccount:billing-breaker-runtime@n8-memory-palace.iam.gserviceaccount.com" \
     --role=roles/billing.projectManager || true
   if ! project_policy="$(
     gcloud projects get-iam-policy n8-memory-palace --format=json
   )"; then
     echo "project policy lookup failed; detach-role removal is not proved" >&2
     exit 1
   fi
   if ! printf '%s' "${project_policy}" | \
     python3 deployment_checks.py exact-project-role \
       --role=roles/billing.projectManager --state=absent; then
     echo "detach-role validator failed; removal is not proved" >&2
     exit 1
   fi
   ```

   The removal command is allowed to report an already-absent binding, but the
   policy read and exact empty-role validator must both succeed.

3. Capture every subscription attached to the dedicated topic from the
   topic-side Pub/Sub list, including subscriptions owned by another project,
   and independently capture every matching Eventarc trigger. Then delete the
   function, triggers, Cloud Run service, and all captured subscriptions. This
   sweep includes an orphan left by a partial Eventarc teardown. If the human
   cannot delete a cross-project subscription, detach it using topic authority;
   detached messages are deleted and the subscription cannot be reattached.
   The current `gcloud functions delete` command does not take `--gen2`.
   Deleting a Pub/Sub topic alone does not delete its subscriptions or retained
   backlog, so topic-side absence is proved before topic deletion. Google
   documents [topic deletion](https://docs.cloud.google.com/pubsub/docs/delete-topic)
   and [subscription detachment](https://docs.cloud.google.com/pubsub/docs/detach-subscriptions).

   ```sh
   if ! subscription_before_json="$(
     gcloud pubsub topics list-subscriptions billing-breaker \
       --project=n8-memory-palace --format=json
   )"; then
     echo "subscription lookup failed; topic-wide queue capture is not proved" >&2
     exit 1
   fi
   if ! subscription_rows="$(
     printf '%s' "${subscription_before_json}" | \
       python3 deployment_checks.py topic-subscriptions --state=list
   )"; then
     echo "topic-wide queue parsing failed; queue identity is not proved" >&2
     exit 1
   fi
   if ! eventarc_before_json="$(
     gcloud eventarc triggers list \
       --location=us-central1 --project=n8-memory-palace --format=json
   )"; then
     echo "Eventarc lookup failed; transport capture is not proved" >&2
     exit 1
   fi
   if ! trigger_rows="$(EVENTARC_JSON="${eventarc_before_json}" python3 - <<'PY'
import json
import os

topic = "projects/n8-memory-palace/topics/billing-breaker"
triggers = json.loads(os.environ["EVENTARC_JSON"])
if not isinstance(triggers, list):
    raise SystemExit("Eventarc list response is not an array")
for trigger in triggers:
    pubsub = trigger.get("transport", {}).get("pubsub", {})
    if pubsub.get("topic") != topic:
        continue
    name = trigger.get("name")
    if not isinstance(name, str) or not name.startswith(
        "projects/n8-memory-palace/locations/us-central1/triggers/"
    ):
        raise SystemExit("matching Eventarc trigger name is malformed")
    print(name)
PY
   )"; then
     echo "Eventarc transport parsing failed; trigger identity is not proved" >&2
     exit 1
   fi
   gcloud functions delete billing-breaker \
     --region=us-central1 --project=n8-memory-palace --quiet || true
   while IFS= read -r trigger_resource; do
     [[ -z "${trigger_resource}" ]] && continue
     gcloud eventarc triggers delete "${trigger_resource##*/}" \
       --location=us-central1 --project=n8-memory-palace --quiet || true
   done <<<"${trigger_rows}"
   gcloud run services delete billing-breaker \
     --region=us-central1 --project=n8-memory-palace --quiet || true

   if ! function_list="$(
     gcloud functions list --v2 --regions=us-central1 \
       --project=n8-memory-palace --format=json
   )"; then
     echo "function list failed; deletion is not proved" >&2
     exit 1
   fi
   if ! printf '%s' "${function_list}" | python3 deployment_checks.py absent \
     --field=name \
     --value=projects/n8-memory-palace/locations/us-central1/functions/billing-breaker; then
     echo "function validator failed; deletion is not proved" >&2
     exit 1
   fi
   if ! run_service_list="$(
     gcloud run services list --region=us-central1 \
       --project=n8-memory-palace --format=json
   )"; then
     echo "Cloud Run list failed; deletion is not proved" >&2
     exit 1
   fi
   if ! printf '%s' "${run_service_list}" | python3 deployment_checks.py absent \
     --field=metadata.name --value=billing-breaker; then
     echo "Cloud Run validator failed; deletion is not proved" >&2
     exit 1
   fi
   if ! eventarc_after_json="$(
     gcloud eventarc triggers list \
       --location=us-central1 --project=n8-memory-palace --format=json
   )"; then
     echo "Eventarc lookup failed; trigger removal is not proved" >&2
     exit 1
   fi
   if ! printf '%s' "${eventarc_after_json}" | \
     python3 deployment_checks.py eventarc-isolation \
       --topic-resource=projects/n8-memory-palace/topics/billing-breaker \
       --function-resource=projects/n8-memory-palace/locations/us-central1/functions/billing-breaker \
       --run-service-name=billing-breaker \
       --run-service-resource=projects/n8-memory-palace/locations/us-central1/services/billing-breaker; then
     echo "Eventarc validator failed; trigger removal is not proved" >&2
     exit 1
   fi
   while IFS= read -r subscription_resource; do
     [[ -z "${subscription_resource}" ]] && continue
     if ! gcloud pubsub subscriptions delete "${subscription_resource}" --quiet; then
       gcloud pubsub topics detach-subscription "${subscription_resource}" \
         --quiet || true
     fi
   done <<<"${subscription_rows}"
   if ! subscription_after_json="$(
     gcloud pubsub topics list-subscriptions billing-breaker \
       --project=n8-memory-palace --format=json
   )"; then
     echo "topic-side subscription list failed; queue removal is not proved" >&2
     exit 1
   fi
   if ! printf '%s' "${subscription_after_json}" | \
     python3 deployment_checks.py topic-subscriptions --state=empty; then
     echo "a topic-attached subscription remains; queue removal is not proved" >&2
     exit 1
   fi
   ```

   Stop if any successful list still contains the function, service, matching
   trigger, or topic-attached subscription. Ignored delete/detach status supports
   a partially completed cleanup; it never substitutes for the later list proof.

4. Delete the dedicated topic to destroy the old delivery path. Remove any
   temporary build roles left by a failed apply, verify no D2 project binding
   remains, then delete all three identities. Successful lists must prove every
   exact resource absent:

   ```sh
   gcloud pubsub topics delete billing-breaker \
     --project=n8-memory-palace --quiet || true
   for role in roles/artifactregistry.writer roles/logging.logWriter roles/storage.objectViewer; do
     gcloud projects remove-iam-policy-binding n8-memory-palace \
       --member="serviceAccount:billing-breaker-build@n8-memory-palace.iam.gserviceaccount.com" \
       --role="${role}" || true
   done
   if ! project_policy="$(
     gcloud projects get-iam-policy n8-memory-palace --format=json
   )"; then
     echo "project policy lookup failed; D2 IAM cleanup is not proved" >&2
     exit 1
   fi
   if ! printf '%s' "${project_policy}" | \
     python3 deployment_checks.py exact-project-role \
       --role=roles/billing.projectManager --state=absent; then
     echo "detach-role validator failed; D2 IAM cleanup is not proved" >&2
     exit 1
   fi
   for role in roles/artifactregistry.writer roles/logging.logWriter roles/storage.objectViewer; do
     if ! printf '%s' "${project_policy}" | \
       python3 deployment_checks.py project-role \
         --role="${role}" \
         --member="serviceAccount:billing-breaker-build@n8-memory-palace.iam.gserviceaccount.com" \
         --state=absent; then
       echo "build-role validator failed; D2 IAM cleanup is not proved" >&2
       exit 1
     fi
   done
   gcloud iam service-accounts delete \
     billing-breaker-runtime@n8-memory-palace.iam.gserviceaccount.com \
     --project=n8-memory-palace --quiet || true
   gcloud iam service-accounts delete \
     billing-breaker-trigger@n8-memory-palace.iam.gserviceaccount.com \
     --project=n8-memory-palace --quiet || true
   gcloud iam service-accounts delete \
     billing-breaker-build@n8-memory-palace.iam.gserviceaccount.com \
     --project=n8-memory-palace --quiet || true
   if ! topic_list="$(
     gcloud pubsub topics list --project=n8-memory-palace --format=json
   )"; then
     echo "topic list failed; deletion is not proved" >&2
     exit 1
   fi
   if ! printf '%s' "${topic_list}" | python3 deployment_checks.py absent \
     --field=name \
     --value=projects/n8-memory-palace/topics/billing-breaker; then
     echo "topic validator failed; deletion is not proved" >&2
     exit 1
   fi
   if ! service_account_list="$(
     gcloud iam service-accounts list \
       --project=n8-memory-palace --format=json
   )"; then
     echo "service-account list failed; deletion is not proved" >&2
     exit 1
   fi
   for service_account in billing-breaker-runtime billing-breaker-trigger billing-breaker-build; do
     if ! printf '%s' "${service_account_list}" | \
       python3 deployment_checks.py absent \
         --field=email \
         --value="${service_account}@n8-memory-palace.iam.gserviceaccount.com"; then
       echo "service-account validator failed; deletion is not proved" >&2
       exit 1
     fi
   done
   ```

   Stop before identity deletion if any exact IAM absence check fails.

5. Only after steps 1–4 pass, reattach the known open billing account and
   verify both fields:

   ```sh
   export BILLING_ACCOUNT_ID=000000-000000-000000
   gcloud billing projects link n8-memory-palace \
     --billing-account="${BILLING_ACCOUNT_ID}"
   if ! billing_json="$(
     gcloud billing projects describe n8-memory-palace --format=json
   )"; then
     echo "billing lookup failed; reattachment is not proved" >&2
     exit 1
   fi
   if ! printf '%s' "${billing_json}" | python3 deployment_checks.py billing \
     --billing-account-id="${BILLING_ACCOUNT_ID}"; then
     echo "billing validator failed; reattachment is not proved" >&2
     exit 1
   fi
   ```

   The validator requires `billingEnabled: true` and exactly
   `billingAccounts/${BILLING_ACCOUNT_ID}`.

6. Inspect Cloud SQL and Cloud Run, restore/redeploy D1 where necessary, and
   repeat its cloud round trip. Reattaching billing does not guarantee every
   resource resumes automatically.
7. Rearm only when the current budget period is below its limit (or a new
   period has begun), every old D2 resource is absent, and recovery is verified.
   Run the full preflight and `deploy.sh --apply` again; it will create fresh
   identities and a fresh queue.

If `deploy.sh --apply` fails, its trap attempts to revoke applicable detach and
temporary build roles and then proves their absence from a fresh project-policy
read. A `CRITICAL` message or exit 99 means the proof failed: assume detach
authority remains active and disconnect the budget immediately. The script
deliberately leaves created resources for inspection. Verify billing is still
enabled, disconnect the budget if it was wired, then perform steps 1–4 before
any retry. Never work around the script by reusing those resources.

Revisit this package when Google Spend Caps becomes generally available and
covers the project's complete Cloud Run plus Cloud SQL spend surface.
