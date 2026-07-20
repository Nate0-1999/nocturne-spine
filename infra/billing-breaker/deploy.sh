#!/usr/bin/env bash
# HUMAN-ONLY: --apply mutates IAM, Pub/Sub, Cloud Run functions, and a billing budget.

set -Eeuo pipefail

readonly PROJECT_ID="n8-memory-palace"
readonly REGION="us-central1"
readonly TOPIC_ID="billing-breaker"
readonly FUNCTION_NAME="billing-breaker"
readonly RUNTIME_SA_ID="billing-breaker-runtime"
readonly TRIGGER_SA_ID="billing-breaker-trigger"
readonly BUILD_SA_ID="billing-breaker-build"
readonly SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly CHECKS="${SOURCE_DIR}/deployment_checks.py"
readonly TOPIC_RESOURCE="projects/${PROJECT_ID}/topics/${TOPIC_ID}"
readonly FUNCTION_RESOURCE="projects/${PROJECT_ID}/locations/${REGION}/functions/${FUNCTION_NAME}"
readonly RUN_SERVICE_RESOURCE="projects/${PROJECT_ID}/locations/${REGION}/services/${FUNCTION_NAME}"
readonly RUNTIME_SA_EMAIL="${RUNTIME_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
readonly TRIGGER_SA_EMAIL="${TRIGGER_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
readonly BUILD_SA_EMAIL="${BUILD_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
readonly BUILD_SA_RESOURCE="projects/${PROJECT_ID}/serviceAccounts/${BUILD_SA_EMAIL}"
readonly BUDGET_PUBLISHER="billing-budget-alert@system.gserviceaccount.com"
readonly RUNTIME_MEMBER="serviceAccount:${RUNTIME_SA_EMAIL}"
readonly TRIGGER_MEMBER="serviceAccount:${TRIGGER_SA_EMAIL}"
readonly BUILD_MEMBER="serviceAccount:${BUILD_SA_EMAIL}"
readonly -a BUILD_ROLES=(
    "roles/artifactregistry.writer"
    "roles/logging.logWriter"
    "roles/storage.objectViewer"
)

usage() {
    printf '%s\n' \
        "usage: BILLING_ACCOUNT_ID=... BUDGET_RESOURCE=billingAccounts/.../budgets/... $0 --dry-run" \
        "       CONFIRM_D2_PROJECT=n8-memory-palace BILLING_ACCOUNT_ID=... BUDGET_RESOURCE=... $0 --apply"
}

if [[ $# -ne 1 || ( "$1" != "--dry-run" && "$1" != "--apply" ) ]]; then
    usage >&2
    exit 2
fi
readonly MODE="$1"

: "${BILLING_ACCOUNT_ID:?set BILLING_ACCOUNT_ID to the existing budget's account ID}"
: "${BUDGET_RESOURCE:?set BUDGET_RESOURCE to the existing budget's full resource name}"

if [[ ! "$BUDGET_RESOURCE" =~ ^billingAccounts/([^/]+)/budgets/([^/]+)$ ]]; then
    printf 'BUDGET_RESOURCE must be billingAccounts/ACCOUNT_ID/budgets/BUDGET_ID\n' >&2
    exit 2
fi
readonly RESOURCE_ACCOUNT_ID="${BASH_REMATCH[1]}"
readonly BUDGET_ID="${BASH_REMATCH[2]}"
if [[ "$RESOURCE_ACCOUNT_ID" != "$BILLING_ACCOUNT_ID" ]]; then
    printf 'BILLING_ACCOUNT_ID does not match BUDGET_RESOURCE\n' >&2
    exit 2
fi

print_plan() {
    cat <<EOF
HUMAN-ONLY D2 plan; no command below was executed.
Read-only preflight: reject credential overrides; verify the human identity, ACTIVE project, enabled billing link, exact billing-account-owned monthly whole-project USD 100.00 budget, and permission-derived direct project plus billing-account access boundaries.
Require interactive confirmation naming ${PROJECT_ID}, ${BUDGET_RESOURCE}, billingAccounts/${BILLING_ACCOUNT_ID}, DETACH BILLING, and current cost below USD 100.
Enable only the documented deployment APIs in ${PROJECT_ID}.
Require successful list checks proving the topic, function, Cloud Run service, conflicting Eventarc triggers, and three D2 service accounts are absent.
gcloud pubsub topics create ${TOPIC_ID} --project=${PROJECT_ID}
gcloud iam service-accounts create ${RUNTIME_SA_ID} --project=${PROJECT_ID}
gcloud iam service-accounts create ${TRIGGER_SA_ID} --project=${PROJECT_ID}
gcloud iam service-accounts create ${BUILD_SA_ID} --project=${PROJECT_ID}
Temporarily grant the build identity Artifact Registry Writer, Logs Writer, and Storage Object Viewer; remove all three immediately after the build.
gcloud functions deploy ${FUNCTION_NAME} --gen2 --project=${PROJECT_ID} --region=${REGION} --runtime=python312 --source=${SOURCE_DIR} --entry-point=stop_billing --trigger-topic=${TOPIC_ID} --trigger-location=${REGION} --run-service-account=${RUNTIME_SA_EMAIL} --trigger-service-account=${TRIGGER_SA_EMAIL} --build-service-account=${BUILD_SA_RESOURCE} --set-env-vars=EXPECTED_BILLING_ACCOUNT_ID=${BILLING_ACCOUNT_ID},EXPECTED_BUDGET_ID=${BUDGET_ID} --no-retry --no-allow-unauthenticated --min-instances=0 --max-instances=1
gcloud run services add-iam-policy-binding ${FUNCTION_NAME} --project=${PROJECT_ID} --region=${REGION} --member=${TRIGGER_MEMBER} --role=roles/run.invoker
gcloud pubsub topics add-iam-policy-binding ${TOPIC_ID} --project=${PROJECT_ID} --member=serviceAccount:${BUDGET_PUBLISHER} --role=roles/pubsub.publisher
Validate the deployed function, its no-retry policy, runtime/build/trigger identities, private Invoker policy, exact topic policy, healthy exact Eventarc trigger/transport subscription, empty subscription policy, and absence of Pub/Sub message transforms before granting detach authority.
gcloud projects add-iam-policy-binding ${PROJECT_ID} --project=${PROJECT_ID} --member=${RUNTIME_MEMBER} --role=roles/billing.projectManager
gcloud billing budgets update ${BUDGET_RESOURCE} --project=${PROJECT_ID} --notifications-rule-pubsub-topic=${TOPIC_RESOURCE}
Assert all armed state; on any later error, revoke applicable detach/build roles and prove their absence or emit a CRITICAL warning.
EOF
}

if [[ "$MODE" == "--dry-run" ]]; then
    print_plan
    exit 0
fi

if [[ "${CONFIRM_D2_PROJECT:-}" != "$PROJECT_ID" ]]; then
    printf 'Refusing --apply. Set CONFIRM_D2_PROJECT=%s after reading README.md.\n' "$PROJECT_ID" >&2
    exit 2
fi
if [[ ! -t 0 || ! -t 1 ]]; then
    printf 'Refusing --apply without an interactive terminal.\n' >&2
    exit 2
fi

command -v gcloud >/dev/null || { printf 'gcloud is required\n' >&2; exit 2; }
command -v python3 >/dev/null || { printf 'python3 is required for validation\n' >&2; exit 2; }

log() {
    printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

check_json() {
    local json="$1"
    shift
    printf '%s' "$json" | python3 "$CHECKS" "$@"
}

describe_role() {
    local role="$1"
    local owner
    local role_id
    if [[ "$role" =~ ^roles/[A-Za-z0-9_.]+$ ]]; then
        gcloud iam roles describe "$role" --format=json
        return
    fi
    if [[ "$role" =~ ^projects/([^/]+)/roles/([^/]+)$ ]]; then
        owner="${BASH_REMATCH[1]}"
        role_id="${BASH_REMATCH[2]}"
        if [[ "$owner" != "$PROJECT_ID" ]]; then
            printf 'Refusing a custom project role owned by %s\n' "$owner" >&2
            return 1
        fi
        gcloud iam roles describe "$role_id" --project="$owner" --format=json
        return
    fi
    if [[ "$role" =~ ^organizations/([0-9]+)/roles/([^/]+)$ ]]; then
        owner="${BASH_REMATCH[1]}"
        role_id="${BASH_REMATCH[2]}"
        gcloud iam roles describe "$role_id" --organization="$owner" --format=json
        return
    fi
    printf 'Unsupported project role resource: %s\n' "$role" >&2
    return 1
}

check_project_access() {
    local policy="$1"
    local project_number="$2"
    local runtime_state="$3"
    local binding_rows
    local members_json
    local role
    local role_json
    binding_rows="$(check_json "$policy" project-bindings)"
    while IFS=$'\t' read -r role members_json; do
        if [[ -z "$role" ]]; then
            continue
        fi
        role_json="$(describe_role "$role")"
        check_json "$role_json" role-access \
            --role-name "$role" \
            --members-json "$members_json" \
            --trusted-member "user:${active_account}" \
            --runtime-member "$RUNTIME_MEMBER" \
            --project-number "$project_number" \
            --runtime-state "$runtime_state"
    done <<<"$binding_rows"
}

check_billing_account_access() {
    local policy="$1"
    local binding_rows
    local members_json
    local role
    local role_json
    binding_rows="$(check_json "$policy" project-bindings)"
    while IFS=$'\t' read -r role members_json; do
        if [[ -z "$role" ]]; then
            continue
        fi
        role_json="$(describe_role "$role")"
        check_json "$role_json" billing-role-access \
            --role-name "$role" \
            --members-json "$members_json" \
            --trusted-member "user:${active_account}"
    done <<<"$binding_rows"
}

check_message_path() {
    local function_json="$1"
    local attached_json
    local eventarc_json
    local subscription_json
    local subscription_policy
    local subscription_resource
    local topic_json
    local trigger_resource

    topic_json="$(
        gcloud pubsub topics describe "$TOPIC_ID" \
            --project="$PROJECT_ID" \
            --format=json
    )"
    check_json "$topic_json" message-resource \
        --resource-label "D2 topic" \
        --expected-name "$TOPIC_RESOURCE"

    attached_json="$(
        gcloud pubsub topics list-subscriptions "$TOPIC_ID" \
            --project="$PROJECT_ID" \
            --format=json
    )"
    subscription_resource="$(
        check_json "$attached_json" topic-subscriptions \
            --state single \
            --project-id "$PROJECT_ID"
    )"
    subscription_json="$(
        gcloud pubsub subscriptions describe "$subscription_resource" --format=json
    )"
    check_json "$subscription_json" message-resource \
        --resource-label "D2 Eventarc subscription" \
        --expected-name "$subscription_resource" \
        --expected-topic "$TOPIC_RESOURCE"
    subscription_policy="$(
        gcloud pubsub subscriptions get-iam-policy "$subscription_resource" \
            --format=json
    )"
    check_json "$subscription_policy" empty-policy \
        --resource "D2 Eventarc subscription"

    trigger_resource="$(
        check_json "$function_json" function-trigger --region "$REGION"
    )"
    eventarc_json="$(
        gcloud eventarc triggers describe "${trigger_resource##*/}" \
            --location="$REGION" \
            --project="$PROJECT_ID" \
            --format=json
    )"
    check_json "$eventarc_json" eventarc-trigger \
        --expected-name "$trigger_resource" \
        --topic-resource "$TOPIC_RESOURCE" \
        --subscription-resource "$subscription_resource" \
        --trigger-service-account "$TRIGGER_SA_EMAIL" \
        --function-resource "$FUNCTION_RESOURCE" \
        --run-service-name "$FUNCTION_NAME" \
        --run-service-resource "$RUN_SERVICE_RESOURCE" \
        --region "$REGION"
}

for auth_property in \
    auth/impersonate_service_account \
    auth/access_token_file \
    auth/credential_file_override; do
    if ! auth_override="$(gcloud config get-value "$auth_property")"; then
        printf 'Unable to verify effective gcloud property %s\n' "$auth_property" >&2
        exit 1
    fi
    if [[ -n "$auth_override" && "$auth_override" != "(unset)" ]]; then
        printf 'Refusing effective gcloud credential override %s=%s\n' \
            "$auth_property" "$auth_override" >&2
        exit 1
    fi
done

active_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)')"
if [[ -z "$active_account" || "$active_account" == *$'\n'* ]]; then
    printf 'Exactly one active gcloud human account is required\n' >&2
    exit 1
fi
if [[ "$active_account" == *.gserviceaccount.com ]]; then
    printf 'Refusing service-account credentials for this human-only deployment\n' >&2
    exit 1
fi
log "active human deployer: ${active_account}"

project_json="$(
    gcloud projects describe "$PROJECT_ID" \
        --project="$PROJECT_ID" \
        --format=json
)"
PROJECT_JSON="$project_json" python3 - <<'PY'
import json
import os

project = json.loads(os.environ["PROJECT_JSON"])
if project.get("lifecycleState") != "ACTIVE":
    raise SystemExit("target project is not ACTIVE")
if not str(project.get("projectNumber", "")).isdigit():
    raise SystemExit("target project number is missing")
PY
project_number="$(
    PROJECT_JSON="$project_json" python3 - <<'PY'
import json
import os

print(json.loads(os.environ["PROJECT_JSON"])["projectNumber"])
PY
)"

billing_json="$(
    gcloud billing projects describe "$PROJECT_ID" \
        --project="$PROJECT_ID" \
        --format=json
)"
check_json "$billing_json" billing --billing-account-id "$BILLING_ACCOUNT_ID"

budget_json="$(
    gcloud billing budgets describe "$BUDGET_RESOURCE" \
        --project="$PROJECT_ID" \
        --format=json
)"
check_json "$budget_json" budget --project-number "$project_number"

billing_account_policy="$(
    gcloud billing accounts get-iam-policy "$BILLING_ACCOUNT_ID" --format=json
)"
check_billing_account_access "$billing_account_policy"

project_policy="$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json)"
check_project_access "$project_policy" "$project_number" absent
check_json "$project_policy" exact-project-role \
    --role roles/billing.projectManager --state absent

printf '%s\n' \
    "STOP unless an off-project backup exists, the current-period actual cost shown" \
    "in Cloud Billing is below USD 100, and every inherited/custom principal with" \
    "billing.budgets.update, billing.resourcebudgets.write," \
    "billing.accounts.setIamPolicy, billing-account closure/association changes," \
    "topic/subscription or Eventarc trigger update/IAM, attachment/detachment," \
    "pubsub.topics.publish, run.routes.invoke," \
    "service-account" \
    "token/key creation, or service-account" \
    "attachment is trusted as a destructive administrator."
readonly EXPECTED_CONFIRMATION="DETACH BILLING ${PROJECT_ID} ${BUDGET_RESOURCE} billingAccounts/${BILLING_ACCOUNT_ID} CURRENT COST BELOW 100"
printf 'Type exactly:\n%s\n> ' "$EXPECTED_CONFIRMATION"
IFS= read -r confirmation
if [[ "$confirmation" != "$EXPECTED_CONFIRMATION" ]]; then
    printf 'Confirmation did not match; nothing was changed.\n' >&2
    exit 2
fi

log "enabling the documented deployment APIs"
gcloud services enable \
    artifactregistry.googleapis.com \
    billingbudgets.googleapis.com \
    cloudbilling.googleapis.com \
    cloudbuild.googleapis.com \
    cloudfunctions.googleapis.com \
    eventarc.googleapis.com \
    iam.googleapis.com \
    logging.googleapis.com \
    pubsub.googleapis.com \
    run.googleapis.com \
    --project="$PROJECT_ID" \
    --quiet

topic_list="$(gcloud pubsub topics list --project="$PROJECT_ID" --format=json)"
check_json "$topic_list" absent --field name --value "$TOPIC_RESOURCE"

function_list="$(
    gcloud functions list \
        --v2 \
        --regions="$REGION" \
        --project="$PROJECT_ID" \
        --format=json
)"
check_json "$function_list" absent --field name --value "$FUNCTION_RESOURCE"

run_service_list="$(
    gcloud run services list \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --format=json
)"
check_json "$run_service_list" absent --field metadata.name --value "$FUNCTION_NAME"

eventarc_list="$(
    gcloud eventarc triggers list \
        --location="$REGION" \
        --project="$PROJECT_ID" \
        --format=json
)"
check_json "$eventarc_list" eventarc-isolation \
    --topic-resource "$TOPIC_RESOURCE" \
    --function-resource "$FUNCTION_RESOURCE" \
    --run-service-name "$FUNCTION_NAME" \
    --run-service-resource "$RUN_SERVICE_RESOURCE"

service_account_list="$(
    gcloud iam service-accounts list --project="$PROJECT_ID" --format=json
)"
for service_account in "$RUNTIME_SA_EMAIL" "$TRIGGER_SA_EMAIL" "$BUILD_SA_EMAIL"; do
    check_json "$service_account_list" absent --field email --value "$service_account"
done

build_cleanup_required=0
detach_cleanup_required=0
rollback_on_error() {
    local status=$?
    local reason="$1"
    local cleanup_failed=0
    local cleanup_policy
    case "$reason" in
        INT) status=130 ;;
        TERM) status=143 ;;
        HUP) status=129 ;;
        EXIT)
            if (( status == 0 )); then
                status=1
            fi
            ;;
    esac
    trap - ERR EXIT INT TERM HUP
    set +e
    if (( detach_cleanup_required == 1 )); then
        log "ERROR rollback: revoking the runtime detach authority"
        gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
            --project="$PROJECT_ID" \
            --member="$RUNTIME_MEMBER" \
            --role=roles/billing.projectManager \
            --quiet >/dev/null 2>&1
        if ! cleanup_policy="$(
            gcloud projects get-iam-policy "$PROJECT_ID" --format=json
        )" || ! check_json "$cleanup_policy" exact-project-role \
            --role roles/billing.projectManager \
            --state absent; then
            cleanup_failed=1
        fi
    fi
    if (( build_cleanup_required == 1 )); then
        for role in "${BUILD_ROLES[@]}"; do
            log "ERROR rollback: revoking possible temporary build role ${role}"
            gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
                --project="$PROJECT_ID" \
                --member="$BUILD_MEMBER" \
                --role="$role" \
                --quiet >/dev/null 2>&1
        done
        if ! cleanup_policy="$(
            gcloud projects get-iam-policy "$PROJECT_ID" --format=json
        )"; then
            cleanup_failed=1
        else
            for role in "${BUILD_ROLES[@]}"; do
                if ! check_json "$cleanup_policy" project-role \
                    --role "$role" --member "$BUILD_MEMBER" --state absent; then
                    cleanup_failed=1
                fi
            done
        fi
    fi
    if (( cleanup_failed == 1 )); then
        printf 'CRITICAL: D2 IAM cleanup could not be proven; detach authority may still be active.\n' >&2
        printf 'Immediately disconnect the budget and run the exact IAM removal commands in README.md.\n' >&2
        exit 99
    fi
    printf 'D2 apply stopped; destructive and build IAM absence was verified where applicable.\n' >&2
    printf 'Do not rerun; follow README.md failed-apply cleanup for created resources.\n' >&2
    exit "$status"
}
trap 'rollback_on_error ERR' ERR
trap 'rollback_on_error EXIT' EXIT
trap 'rollback_on_error INT' INT
trap 'rollback_on_error TERM' TERM
trap 'rollback_on_error HUP' HUP

log "creating a fresh dedicated topic"
gcloud pubsub topics create "$TOPIC_ID" --project="$PROJECT_ID" --quiet
empty_topic_policy="$(
    gcloud pubsub topics get-iam-policy "$TOPIC_ID" \
        --project="$PROJECT_ID" \
        --format=json
)"
check_json "$empty_topic_policy" empty-policy --resource "Pub/Sub topic"

log "creating separated runtime, trigger, and temporary build identities"
gcloud iam service-accounts create "$RUNTIME_SA_ID" \
    --project="$PROJECT_ID" \
    --display-name="Billing breaker runtime" \
    --quiet
gcloud iam service-accounts create "$TRIGGER_SA_ID" \
    --project="$PROJECT_ID" \
    --display-name="Billing breaker trigger" \
    --quiet
gcloud iam service-accounts create "$BUILD_SA_ID" \
    --project="$PROJECT_ID" \
    --display-name="Billing breaker one-shot build" \
    --quiet

for service_account in "$RUNTIME_SA_EMAIL" "$TRIGGER_SA_EMAIL" "$BUILD_SA_EMAIL"; do
    user_keys="$(
        gcloud iam service-accounts keys list \
            --iam-account="$service_account" \
            --managed-by=user \
            --format='value(name)'
    )"
    if [[ -n "$user_keys" ]]; then
        printf 'Refusing D2 identity %s with user-managed keys\n' "$service_account" >&2
        exit 1
    fi
    service_account_policy="$(
        gcloud iam service-accounts get-iam-policy "$service_account" \
            --project="$PROJECT_ID" \
            --format=json
    )"
    check_json "$service_account_policy" empty-policy \
        --resource "service account ${service_account}"
done

log "granting the documented build roles to the isolated build identity"
build_cleanup_required=1
for role in "${BUILD_ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --project="$PROJECT_ID" \
        --member="$BUILD_MEMBER" \
        --role="$role" \
        --quiet >/dev/null
done

log "deploying the private Python 3.12 function with retries disabled"
gcloud functions deploy "$FUNCTION_NAME" \
    --gen2 \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --runtime=python312 \
    --source="$SOURCE_DIR" \
    --entry-point=stop_billing \
    --trigger-topic="$TOPIC_ID" \
    --trigger-location="$REGION" \
    --run-service-account="$RUNTIME_SA_EMAIL" \
    --trigger-service-account="$TRIGGER_SA_EMAIL" \
    --build-service-account="$BUILD_SA_RESOURCE" \
    --set-env-vars="EXPECTED_BILLING_ACCOUNT_ID=${BILLING_ACCOUNT_ID},EXPECTED_BUDGET_ID=${BUDGET_ID}" \
    --no-retry \
    --no-allow-unauthenticated \
    --min-instances=0 \
    --max-instances=1 \
    --quiet

log "removing every temporary build permission before arming"
for role in "${BUILD_ROLES[@]}"; do
    gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
        --project="$PROJECT_ID" \
        --member="$BUILD_MEMBER" \
        --role="$role" \
        --quiet >/dev/null
done
project_policy="$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json)"
for role in "${BUILD_ROLES[@]}"; do
    check_json "$project_policy" project-role \
        --role "$role" --member "$BUILD_MEMBER" --state absent
done
build_cleanup_required=0

log "allowing only the trigger identity to invoke this Cloud Run service"
gcloud run services add-iam-policy-binding "$FUNCTION_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --member="$TRIGGER_MEMBER" \
    --role=roles/run.invoker \
    --quiet >/dev/null

log "authorizing only the documented Cloud Billing budget publisher"
gcloud pubsub topics add-iam-policy-binding "$TOPIC_ID" \
    --project="$PROJECT_ID" \
    --member="serviceAccount:${BUDGET_PUBLISHER}" \
    --role=roles/pubsub.publisher \
    --quiet >/dev/null

function_json="$(
    gcloud functions describe "$FUNCTION_NAME" \
        --gen2 \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --format=json
)"
check_json "$function_json" function \
    --runtime-service-account "$RUNTIME_SA_EMAIL" \
    --trigger-service-account "$TRIGGER_SA_EMAIL" \
    --build-service-account-resource "$BUILD_SA_RESOURCE" \
    --topic-resource "$TOPIC_RESOURCE" \
    --expected-billing-account-id "$BILLING_ACCOUNT_ID" \
    --expected-budget-id "$BUDGET_ID" \
    --region "$REGION"

run_policy="$(
    gcloud run services get-iam-policy "$FUNCTION_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --format=json
)"
check_json "$run_policy" run-policy --trigger-service-account "$TRIGGER_SA_EMAIL"

topic_policy="$(
    gcloud pubsub topics get-iam-policy "$TOPIC_ID" \
        --project="$PROJECT_ID" \
        --format=json
)"
check_json "$topic_policy" topic-policy --budget-publisher "$BUDGET_PUBLISHER"
check_message_path "$function_json"

project_policy="$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json)"
check_project_access "$project_policy" "$project_number" absent
check_json "$project_policy" exact-project-role \
    --role roles/billing.projectManager --state absent
for role in "${BUILD_ROLES[@]}"; do
    check_json "$project_policy" project-role \
        --role "$role" --member "$BUILD_MEMBER" --state absent
done
for service_account in "$RUNTIME_SA_EMAIL" "$TRIGGER_SA_EMAIL" "$BUILD_SA_EMAIL"; do
    service_account_policy="$(
        gcloud iam service-accounts get-iam-policy "$service_account" \
            --project="$PROJECT_ID" \
            --format=json
    )"
    check_json "$service_account_policy" empty-policy \
        --resource "service account ${service_account}"
done
billing_account_policy="$(
    gcloud billing accounts get-iam-policy "$BILLING_ACCOUNT_ID" --format=json
)"
check_billing_account_access "$billing_account_policy"

log "granting project-scoped detach authority immediately before budget wiring"
detach_cleanup_required=1
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --project="$PROJECT_ID" \
    --member="$RUNTIME_MEMBER" \
    --role=roles/billing.projectManager \
    --quiet >/dev/null

project_policy="$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json)"
check_json "$project_policy" exact-project-role \
    --role roles/billing.projectManager --member "$RUNTIME_MEMBER" --state exact

log "wiring the already-validated budget last"
gcloud billing budgets update "$BUDGET_RESOURCE" \
    --project="$PROJECT_ID" \
    --notifications-rule-pubsub-topic="$TOPIC_RESOURCE" \
    --quiet

budget_json="$(
    gcloud billing budgets describe "$BUDGET_RESOURCE" \
        --project="$PROJECT_ID" \
        --format=json
)"
check_json "$budget_json" budget \
    --project-number "$project_number" \
    --expected-topic "$TOPIC_RESOURCE"

billing_json="$(
    gcloud billing projects describe "$PROJECT_ID" \
        --project="$PROJECT_ID" \
        --format=json
)"
check_json "$billing_json" billing --billing-account-id "$BILLING_ACCOUNT_ID"

function_json="$(
    gcloud functions describe "$FUNCTION_NAME" \
        --gen2 \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --format=json
)"
check_json "$function_json" function \
    --runtime-service-account "$RUNTIME_SA_EMAIL" \
    --trigger-service-account "$TRIGGER_SA_EMAIL" \
    --build-service-account-resource "$BUILD_SA_RESOURCE" \
    --topic-resource "$TOPIC_RESOURCE" \
    --expected-billing-account-id "$BILLING_ACCOUNT_ID" \
    --expected-budget-id "$BUDGET_ID" \
    --region "$REGION"

topic_policy="$(
    gcloud pubsub topics get-iam-policy "$TOPIC_ID" \
        --project="$PROJECT_ID" \
        --format=json
)"
check_json "$topic_policy" topic-policy --budget-publisher "$BUDGET_PUBLISHER"
check_message_path "$function_json"

run_policy="$(
    gcloud run services get-iam-policy "$FUNCTION_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --format=json
)"
check_json "$run_policy" run-policy --trigger-service-account "$TRIGGER_SA_EMAIL"

project_policy="$(gcloud projects get-iam-policy "$PROJECT_ID" --format=json)"
check_project_access "$project_policy" "$project_number" present
check_json "$project_policy" exact-project-role \
    --role roles/billing.projectManager --member "$RUNTIME_MEMBER" --state exact
billing_account_policy="$(
    gcloud billing accounts get-iam-policy "$BILLING_ACCOUNT_ID" --format=json
)"
check_billing_account_access "$billing_account_policy"

detach_cleanup_required=0
trap - ERR EXIT INT TERM HUP
log "D2 is armed; run only the below-budget synthetic drill in README.md"
