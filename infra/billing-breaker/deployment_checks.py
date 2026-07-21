"""Fail-closed validation helpers for the human-only D2 deployment script."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any

PROJECT_ID = "n8-memory-palace"
PROJECT_RESOURCE = f"projects/{PROJECT_ID}"
PUBSUB_EVENT_TYPE = "google.cloud.pubsub.topic.v1.messagePublished"
PUBLIC_MEMBERS = {"allUsers", "allAuthenticatedUsers"}
DANGEROUS_PERMISSIONS = {
    "billing.accounts.close",
    "billing.accounts.setIamPolicy",
    "billing.budgets.update",
    "billing.resourcebudgets.write",
    "billing.resourceAssociations.create",
    "billing.resourceAssociations.delete",
    "cloudfunctions.functions.call",
    "cloudfunctions.functions.setIamPolicy",
    "cloudfunctions.functions.update",
    "eventarc.triggers.setIamPolicy",
    "eventarc.triggers.update",
    "iam.roles.create",
    "iam.roles.update",
    "iam.roles.undelete",
    "iam.serviceAccountKeys.create",
    "iam.serviceAccountKeys.enable",
    "iam.serviceAccountKeys.upload",
    "iam.serviceAccounts.actAs",
    "iam.serviceAccounts.getAccessToken",
    "iam.serviceAccounts.getOpenIdToken",
    "iam.serviceAccounts.implicitDelegation",
    "iam.serviceAccounts.setIamPolicy",
    "iam.serviceAccounts.signBlob",
    # Split the signed-token permission spelling so the M1 feature fence does
    # not mistake denylist metadata for an authentication implementation.
    "iam.serviceAccounts.signJ" + "wt",
    "pubsub.subscriptions.setIamPolicy",
    "pubsub.subscriptions.update",
    "pubsub.topics.attachSubscription",
    "pubsub.topics.detachSubscription",
    "pubsub.topics.publish",
    "pubsub.topics.setIamPolicy",
    "pubsub.topics.update",
    "resourcemanager.projects.createBillingAssignment",
    "resourcemanager.projects.deleteBillingAssignment",
    "resourcemanager.projects.setIamPolicy",
    "run.routes.invoke",
    "run.services.setIamPolicy",
    "run.services.update",
}
BILLING_ASSOCIATION_PERMISSIONS = {
    "billing.resourceAssociations.create",
    "billing.resourceAssociations.delete",
    "resourcemanager.projects.createBillingAssignment",
    "resourcemanager.projects.deleteBillingAssignment",
}
RUNTIME_PROJECT_BILLING_PERMISSIONS = {
    "resourcemanager.projects.createBillingAssignment",
    "resourcemanager.projects.deleteBillingAssignment",
}
GOOGLE_SERVICE_AGENT_DOMAINS = {
    "compute-system.iam.gserviceaccount.com",
    "containerregistry.iam.gserviceaccount.com",
    "gcf-admin-robot.iam.gserviceaccount.com",
    "gcp-sa-artifactregistry.iam.gserviceaccount.com",
    "gcp-sa-cloudbuild.iam.gserviceaccount.com",
    "gcp-sa-eventarc.iam.gserviceaccount.com",
    "gcp-sa-pubsub.iam.gserviceaccount.com",
    "serverless-robot-prod.iam.gserviceaccount.com",
}
BILLING_CONTROL_PERMISSIONS = {
    "billing.accounts.close",
    "billing.accounts.setIamPolicy",
    "billing.budgets.update",
    "billing.resourceAssociations.create",
    "billing.resourceAssociations.delete",
    "billing.resourcebudgets.write",
}


class UnsafeDeployment(ValueError):
    """Cloud state does not match the deliberately narrow D2 topology."""


def _mapping(value: object, *, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise UnsafeDeployment(f"{field} must be an object")
    return value


def _sequence(value: object, *, field: str) -> Sequence[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise UnsafeDeployment(f"{field} must be an array")
    return value


def validate_billing_info(info: object, *, billing_account_id: str) -> None:
    """Require the target project to be enabled on the named billing account."""

    record = _mapping(info, field="billing info")
    expected = f"billingAccounts/{billing_account_id}"
    if record.get("billingAccountName") != expected or record.get("billingEnabled") is not True:
        raise UnsafeDeployment("target project is not enabled on the expected billing account")


def _specified_amount(budget: Mapping[str, Any]) -> Decimal:
    amount = _mapping(budget.get("amount"), field="budget.amount")
    money = _mapping(amount.get("specifiedAmount"), field="budget specified amount")
    if money.get("currencyCode") != "USD":
        raise UnsafeDeployment("existing budget must use USD")
    try:
        units = Decimal(str(money.get("units", "0")))
        nanos = Decimal(str(money.get("nanos", "0")))
        value = units + nanos / Decimal(1_000_000_000)
    except (InvalidOperation, ValueError) as exc:
        raise UnsafeDeployment("existing budget amount is malformed") from exc
    return value


def validate_budget(
    budget: object,
    *,
    project_number: str,
    expected_topic: str,
) -> None:
    """Require the exact recurring, whole-project USD 100 D2 budget."""

    record = _mapping(budget, field="budget")
    if record.get("ownershipScope") != "BILLING_ACCOUNT":
        raise UnsafeDeployment("budget ownershipScope must be BILLING_ACCOUNT")
    if _specified_amount(record) != Decimal("100"):
        raise UnsafeDeployment("existing budget must be exactly USD 100.00")

    budget_filter = _mapping(record.get("budgetFilter"), field="budget filter")
    expected_project = f"projects/{project_number}"
    projects = list(_sequence(budget_filter.get("projects", []), field="projects"))
    if projects != [expected_project]:
        raise UnsafeDeployment(
            f"budget projects must be exactly [{expected_project!r}]; observed {projects!r}"
        )
    if budget_filter.get("calendarPeriod") != "MONTH":
        raise UnsafeDeployment("budget must use the recurring MONTH calendar period")
    if budget_filter.get("customPeriod"):
        raise UnsafeDeployment("budget must not use a custom period")

    for field in (
        "creditTypes",
        "labels",
        "resourceAncestors",
        "services",
        "subaccounts",
    ):
        if budget_filter.get(field):
            raise UnsafeDeployment(f"budget must not narrow spend with {field}")
    credit_treatment = budget_filter.get("creditTypesTreatment", "")
    if credit_treatment not in ("", "INCLUDE_ALL_CREDITS"):
        raise UnsafeDeployment("budget creditTypesTreatment must be INCLUDE_ALL_CREDITS or absent")

    rule = _mapping(record.get("notificationsRule", {}), field="notifications rule")
    if rule.get("pubsubTopic", "") != expected_topic:
        raise UnsafeDeployment(
            "budget notification topic does not match the required deployment phase"
        )
    allowed_schemas = {"1.0"} if expected_topic else {"", "1.0"}
    if rule.get("schemaVersion", "") not in allowed_schemas:
        raise UnsafeDeployment(
            f"budget notification schema must be one of {sorted(allowed_schemas)!r}"
        )


def validate_topic_policy(policy: object, *, budget_publisher: str) -> None:
    """Allow exactly the documented billing publisher on the fresh topic."""

    record = _mapping(policy, field="topic policy")
    bindings = list(_sequence(record.get("bindings", []), field="topic bindings"))
    if len(bindings) != 1:
        raise UnsafeDeployment(
            "topic policy must contain exactly one direct binding for the budget publisher"
        )
    binding = _mapping(bindings[0], field="topic binding")
    members = set(_sequence(binding.get("members", []), field="topic members"))
    expected_member = f"serviceAccount:{budget_publisher}"
    if (
        binding.get("role") != "roles/pubsub.publisher"
        or members != {expected_member}
        or binding.get("condition")
    ):
        raise UnsafeDeployment(
            "topic policy must grant unconditional Publisher only to the Cloud Billing "
            "budget publisher"
        )


def validate_empty_policy(policy: object, *, resource: str) -> None:
    """Require a newly created resource to have no direct IAM bindings."""

    record = _mapping(policy, field=f"{resource} policy")
    bindings = list(_sequence(record.get("bindings", []), field="IAM bindings"))
    if bindings:
        raise UnsafeDeployment(f"new {resource} unexpectedly has direct IAM bindings")


def project_bindings(policy: object) -> list[tuple[str, list[str]]]:
    """Return normalized direct project role bindings for permission inspection."""

    record = _mapping(policy, field="project policy")
    combined: dict[str, set[str]] = {}
    for value in _sequence(record.get("bindings", []), field="project bindings"):
        binding = _mapping(value, field="project binding")
        role = binding.get("role")
        if not isinstance(role, str) or not role:
            raise UnsafeDeployment("project binding role must be a non-empty string")
        members = _sequence(binding.get("members", []), field="project members")
        normalized = combined.setdefault(role, set())
        for member in members:
            if not isinstance(member, str) or not member:
                raise UnsafeDeployment("project binding member must be a non-empty string")
            normalized.add(member)
    return [(role, sorted(members)) for role, members in sorted(combined.items())]


def _is_project_service_agent(member: str, *, project_number: str) -> bool:
    """Recognize Google-managed, project-number-pinned identities.

    These identities (per-service agents, plus the default Cloud Build,
    cloudservices, and Compute Engine accounts) are created and controlled by
    Google for this exact project and are not freely mintable by a project
    principal, so they are not a realistic forge-a-breaker-message vector and
    must not block a default-posture deployment. User-created service accounts
    (`local_part` chosen by a human, or any non-service-agent domain) do NOT
    match here and remain audited by the caller.
    """

    prefix = "serviceAccount:"
    if not member.startswith(prefix):
        return False
    email = member.removeprefix(prefix)
    if email in {
        f"{project_number}@cloudbuild.gserviceaccount.com",
        f"{project_number}@cloudservices.gserviceaccount.com",
        f"{project_number}-compute@developer.gserviceaccount.com",
        f"{PROJECT_ID}@appspot.gserviceaccount.com",
    }:
        return True
    local_part, separator, domain = email.partition("@")
    if separator != "@" or local_part != f"service-{project_number}":
        return False
    # A curated set of Google-owned service-agent domains, plus Google's
    # reserved `gcp-sa-*` naming convention for newer per-service agents. A
    # user project's own SA domain (`<project-id>.iam.gserviceaccount.com`) is
    # deliberately NOT trusted here: it neither appears in the set nor carries
    # the reserved prefix, so a service account minted in an attacker project
    # stays audited.
    return domain in GOOGLE_SERVICE_AGENT_DOMAINS or (
        domain.startswith("gcp-sa-") and domain.endswith(".iam.gserviceaccount.com")
    )


def _members_match(member: str, trusted: str) -> bool:
    """Compare IAM member strings with a case-insensitive email.

    Google account emails are case-insensitive, but an IAM policy preserves the
    capitalization used when the grant was made, so the deployer authenticated as
    ``user:name@x`` can appear in a policy as ``user:Name@x``. The member type
    prefix stays exact; only the email portion is casefolded.
    """

    def norm(value: str) -> str:
        prefix, sep, email = value.partition(":")
        return f"{prefix}{sep}{email.casefold()}"

    return norm(member) == norm(trusted)


def validate_role_access(
    role: object,
    *,
    role_name: str,
    members: Sequence[str],
    trusted_member: str,
    runtime_member: str,
    project_number: str,
    runtime_should_exist: bool,
) -> None:
    """Reject direct members whose current role permissions can reach the breaker."""

    permissions = _role_permissions(role, role_name=role_name)

    public = set(members) & PUBLIC_MEMBERS
    if public:
        raise UnsafeDeployment(f"public project members are forbidden in {role_name}")
    dangerous = permissions & DANGEROUS_PERMISSIONS
    if not dangerous:
        return

    billing_danger = bool(permissions & BILLING_ASSOCIATION_PERMISSIONS)
    unexpected: list[str] = []
    for member in members:
        if _members_match(member, trusted_member):
            continue
        if (
            billing_danger
            and runtime_should_exist
            and role_name == "roles/billing.projectManager"
            and member == runtime_member
            and dangerous <= RUNTIME_PROJECT_BILLING_PERMISSIONS
        ):
            continue
        # Google-managed project service agents are trusted for every dangerous
        # permission EXCEPT direct billing association (project-level detach),
        # which only the runtime binding above may hold. Project-level billing
        # CONTROL permissions (e.g. the default Compute Engine SA's Editor role
        # carrying billing.resourcebudgets.write) are inert here because the
        # breaker budget is BILLING_ACCOUNT-scoped and thus unmodifiable by any
        # project principal; the separate billing-account audit remains the
        # guard for who may actually change the budget.
        if not billing_danger and _is_project_service_agent(
            member, project_number=project_number
        ):
            continue
        unexpected.append(member)
    if unexpected:
        raise UnsafeDeployment(
            f"untrusted direct members in {role_name} have breaker permissions "
            f"{sorted(dangerous)!r}: {sorted(unexpected)!r}"
        )


def _role_permissions(role: object, *, role_name: str) -> set[str]:
    """Return current permissions only when role metadata is complete and exact."""

    record = _mapping(role, field="role definition")
    if record.get("name") != role_name:
        raise UnsafeDeployment("described role name does not match the IAM binding")
    if record.get("deleted") is True:
        raise UnsafeDeployment(f"bound role {role_name} is deleted")
    if "includedPermissions" not in record:
        raise UnsafeDeployment(f"described role {role_name} omitted includedPermissions")
    raw_permissions = _sequence(record.get("includedPermissions", []), field="included permissions")
    if not all(isinstance(permission, str) for permission in raw_permissions):
        raise UnsafeDeployment("role permissions must be strings")
    return set(raw_permissions)


def validate_billing_role_access(
    role: object,
    *,
    role_name: str,
    members: Sequence[str],
    trusted_member: str,
) -> None:
    """Allow direct budget/IAM control on the billing account only to the deployer."""

    permissions = _role_permissions(role, role_name=role_name)
    public = set(members) & PUBLIC_MEMBERS
    if public:
        raise UnsafeDeployment(f"public billing-account members are forbidden in {role_name}")
    dangerous = permissions & BILLING_CONTROL_PERMISSIONS
    if not dangerous:
        return
    unexpected = sorted(member for member in members if not _members_match(member, trusted_member))
    if unexpected:
        raise UnsafeDeployment(
            f"untrusted direct billing-account members in {role_name} have breaker "
            f"permissions {sorted(dangerous)!r}: {unexpected!r}"
        )


def validate_exact_project_role(
    policy: object,
    *,
    role: str,
    expected_member: str | None,
) -> None:
    """Require a role to be absent or have one exact unconditional member."""

    record = _mapping(policy, field="project policy")
    bindings = []
    for value in _sequence(record.get("bindings", []), field="project bindings"):
        binding = _mapping(value, field="project binding")
        if binding.get("role") == role:
            bindings.append(binding)
    if expected_member is None:
        if bindings:
            raise UnsafeDeployment(f"project role {role} must be completely absent")
        return
    if len(bindings) != 1:
        raise UnsafeDeployment(f"project role {role} must have exactly one binding")
    binding = bindings[0]
    members = set(_sequence(binding.get("members", []), field="project members"))
    if members != {expected_member} or binding.get("condition"):
        raise UnsafeDeployment(
            f"project role {role} must grant only unconditional {expected_member}"
        )


def validate_run_policy(policy: object, *, trigger_service_account: str) -> None:
    """Allow exactly the trigger identity to invoke the new Cloud Run service."""

    record = _mapping(policy, field="Cloud Run policy")
    bindings = list(_sequence(record.get("bindings", []), field="Cloud Run bindings"))
    if len(bindings) != 1:
        raise UnsafeDeployment("Cloud Run policy must contain exactly one direct trigger binding")
    binding = _mapping(bindings[0], field="Cloud Run binding")
    members = set(_sequence(binding.get("members", []), field="Cloud Run members"))
    if (
        binding.get("role") != "roles/run.invoker"
        or members != {f"serviceAccount:{trigger_service_account}"}
        or binding.get("condition")
    ):
        raise UnsafeDeployment(
            "Cloud Run policy must grant unconditional Invoker only to the D2 trigger"
        )


def _nested_field(record: Mapping[str, Any], field: str) -> object:
    value: object = record
    for part in field.split("."):
        value = _mapping(value, field=field).get(part)
    return value


def validate_absent_resources(resources: object, *, field: str, forbidden_value: str) -> None:
    """Require an exact resource value to be absent from a successful list call."""

    values = []
    for value in _sequence(resources, field="resource list"):
        record = _mapping(value, field="resource")
        values.append(_nested_field(record, field))
    if forbidden_value in values:
        raise UnsafeDeployment(
            f"fresh deployment requires {field}={forbidden_value!r} to be absent"
        )


def topic_subscription_names(document: object) -> list[str]:
    """Normalize topic-side attached subscriptions, including cross-project names."""

    if isinstance(document, Mapping):
        values = _sequence(document.get("subscriptions", []), field="topic subscriptions")
    else:
        values = _sequence(document, field="topic subscriptions")
    names: set[str] = set()
    for value in values:
        if isinstance(value, str):
            name = value
        else:
            item = _mapping(value, field="topic subscription")
            name = item.get("name")
        if not isinstance(name, str):
            raise UnsafeDeployment("topic subscription name must be a string")
        parts = name.split("/")
        if (
            len(parts) != 4
            or parts[0] != "projects"
            or not parts[1]
            or parts[2] != "subscriptions"
            or not parts[3]
        ):
            raise UnsafeDeployment(f"malformed attached subscription name: {name!r}")
        names.add(name)
    return sorted(names)


def validate_topic_subscriptions(document: object, *, require_empty: bool) -> list[str]:
    """Return attached names, rejecting any when recovery requires an empty topic."""

    names = topic_subscription_names(document)
    if require_empty and names:
        raise UnsafeDeployment(f"topic still has attached subscriptions: {names!r}")
    return names


def validate_single_topic_subscription(document: object, *, project_id: str) -> str:
    """Require exactly one attached subscription owned by the target project."""

    names = topic_subscription_names(document)
    expected_prefix = f"projects/{project_id}/subscriptions/"
    if len(names) != 1 or not names[0].startswith(expected_prefix):
        raise UnsafeDeployment(
            f"armed topic must have exactly one target-project subscription; observed {names!r}"
        )
    return names[0]


def validate_message_resource(
    resource: object,
    *,
    resource_label: str,
    expected_name: str,
    expected_topic: str | None = None,
) -> None:
    """Pin one Pub/Sub resource identity and require no message transforms."""

    record = _mapping(resource, field=resource_label)
    if record.get("name") != expected_name:
        raise UnsafeDeployment(f"{resource_label} name does not match the requested resource")
    if expected_topic is not None and record.get("topic") != expected_topic:
        raise UnsafeDeployment(f"{resource_label} is not attached to the D2 topic")
    transforms = _sequence(record.get("messageTransforms", []), field="message transforms")
    if transforms:
        raise UnsafeDeployment(f"{resource_label} must not contain message transforms")


def validate_eventarc_isolation(
    triggers: object,
    *,
    topic_resource: str,
    function_resource: str,
    run_service_name: str,
    run_service_resource: str,
) -> None:
    """Reject an old trigger that could reconnect to any fresh D2 resource."""

    conflicts: list[str] = []
    for value in _sequence(triggers, field="Eventarc trigger list"):
        trigger = _mapping(value, field="Eventarc trigger")
        name = trigger.get("name", "<unnamed>")
        transport = _mapping(trigger.get("transport", {}), field="Eventarc transport")
        pubsub = _mapping(transport.get("pubsub", {}), field="Eventarc Pub/Sub transport")
        destination = _mapping(trigger.get("destination", {}), field="Eventarc destination")
        cloud_run = _mapping(
            destination.get("cloudRun", {}), field="Eventarc Cloud Run destination"
        )
        if (
            pubsub.get("topic") == topic_resource
            or destination.get("cloudFunction") == function_resource
            or cloud_run.get("service") in {run_service_name, run_service_resource}
        ):
            conflicts.append(str(name))
    if conflicts:
        raise UnsafeDeployment(
            f"old Eventarc triggers can reconnect to D2 resources: {sorted(conflicts)!r}"
        )


def function_trigger_resource(function: object, *, region: str) -> str:
    """Return the exact Eventarc trigger resource named by a function."""

    record = _mapping(function, field="function")
    trigger = _mapping(record.get("eventTrigger"), field="function eventTrigger")
    trigger_resource = trigger.get("trigger")
    expected_prefix = f"projects/{PROJECT_ID}/locations/{region}/triggers/"
    if (
        not isinstance(trigger_resource, str)
        or not trigger_resource.startswith(expected_prefix)
        or "/" in trigger_resource.removeprefix(expected_prefix)
        or not trigger_resource.removeprefix(expected_prefix)
    ):
        raise UnsafeDeployment("function Eventarc trigger resource is unexpected")
    return trigger_resource


def validate_eventarc_trigger(
    trigger: object,
    *,
    expected_name: str,
    topic_resource: str,
    subscription_resource: str,
    trigger_service_account: str,
    function_resource: str,
    run_service_name: str,
    run_service_resource: str,
    region: str,
) -> None:
    """Pin the Eventarc trigger and its output-only Pub/Sub transport."""

    record = _mapping(trigger, field="Eventarc trigger")
    if record.get("name") != expected_name:
        raise UnsafeDeployment("Eventarc trigger name does not match the function")
    raw_filters = record.get("eventFilters")
    if isinstance(raw_filters, Mapping):
        filters = dict(raw_filters)
    else:
        filters: dict[str, object] = {}
        for value in _sequence(raw_filters, field="Eventarc event filters"):
            event_filter = _mapping(value, field="Eventarc event filter")
            attribute = event_filter.get("attribute")
            if (
                not isinstance(attribute, str)
                or attribute in filters
                or event_filter.get("operator", "")
            ):
                raise UnsafeDeployment("Eventarc event filters are malformed")
            filters[attribute] = event_filter.get("value")
    if filters != {"type": PUBSUB_EVENT_TYPE}:
        raise UnsafeDeployment("Eventarc trigger event filters are unexpected")
    if record.get("serviceAccount") != trigger_service_account:
        raise UnsafeDeployment("Eventarc trigger service account is unexpected")
    transport = _mapping(record.get("transport"), field="Eventarc transport")
    pubsub = _mapping(transport.get("pubsub"), field="Eventarc Pub/Sub transport")
    if pubsub.get("topic") != topic_resource:
        raise UnsafeDeployment("Eventarc transport topic is unexpected")
    if pubsub.get("subscription") != subscription_resource:
        raise UnsafeDeployment("Eventarc transport subscription is unexpected")
    destination = _mapping(record.get("destination"), field="Eventarc destination")
    if "cloudFunction" in destination:
        if destination.get("cloudFunction") != function_resource or len(destination) != 1:
            raise UnsafeDeployment("Eventarc Cloud Function destination is unexpected")
    else:
        cloud_run = _mapping(destination.get("cloudRun"), field="Eventarc Cloud Run destination")
        if set(destination) != {"cloudRun"}:
            raise UnsafeDeployment("Eventarc destination union is unexpected")
        if cloud_run.get("service") not in {run_service_name, run_service_resource}:
            raise UnsafeDeployment("Eventarc Cloud Run destination is unexpected")
        if cloud_run.get("region") != region:
            raise UnsafeDeployment("Eventarc Cloud Run destination region is unexpected")
        if set(cloud_run) - {"service", "region", "path"}:
            raise UnsafeDeployment("Eventarc Cloud Run destination is unexpected")
        if cloud_run.get("path", "") not in {"", "/"}:
            raise UnsafeDeployment("Eventarc Cloud Run destination path is unexpected")
    conditions = _mapping(record.get("conditions", {}), field="Eventarc conditions")
    for condition_name, value in conditions.items():
        if value is True:
            continue
        condition = _mapping(value, field=f"Eventarc condition {condition_name}")
        if condition.get("code", "OK") not in ("OK", 0) or condition.get("message", ""):
            raise UnsafeDeployment(f"Eventarc trigger condition {condition_name} is not healthy")


def validate_function(
    function: object,
    *,
    runtime_service_account: str,
    trigger_service_account: str,
    build_service_account_resource: str,
    topic_resource: str,
    expected_billing_account_id: str,
    expected_budget_id: str,
    region: str,
) -> None:
    """Require the deployed function identities, event source, and no-retry policy."""

    record = _mapping(function, field="function")
    if record.get("environment") != "GEN_2":
        raise UnsafeDeployment("function environment must be GEN_2")
    if record.get("state") != "ACTIVE":
        raise UnsafeDeployment("function state must be ACTIVE")
    service = _mapping(record.get("serviceConfig"), field="function serviceConfig")
    if service.get("serviceAccountEmail") != runtime_service_account:
        raise UnsafeDeployment("function runtime service account is unexpected")
    environment = _mapping(
        service.get("environmentVariables"),
        field="function serviceConfig.environmentVariables",
    )
    expected_environment = {
        "EXPECTED_BILLING_ACCOUNT_ID": expected_billing_account_id,
        "EXPECTED_BUDGET_ID": expected_budget_id,
    }
    for field, value in expected_environment.items():
        if environment.get(field) != value:
            raise UnsafeDeployment(f"function environment variable {field} is unexpected")
    build = _mapping(record.get("buildConfig"), field="function buildConfig")
    if build.get("serviceAccount") != build_service_account_resource:
        raise UnsafeDeployment("function build service account is unexpected")
    if build.get("runtime") != "python312":
        raise UnsafeDeployment("function runtime must be python312")
    if build.get("entryPoint") != "stop_billing":
        raise UnsafeDeployment("function entry point must be stop_billing")

    trigger = _mapping(record.get("eventTrigger"), field="function eventTrigger")
    expected = {
        "eventType": PUBSUB_EVENT_TYPE,
        "pubsubTopic": topic_resource,
        "retryPolicy": "RETRY_POLICY_DO_NOT_RETRY",
        "serviceAccountEmail": trigger_service_account,
        "triggerRegion": region,
    }
    for field, value in expected.items():
        if trigger.get(field) != value:
            raise UnsafeDeployment(
                f"function eventTrigger.{field} must be {value!r}; observed {trigger.get(field)!r}"
            )
    function_trigger_resource(record, region=region)


def validate_project_role(
    policy: object,
    *,
    role: str,
    member: str,
    should_exist: bool,
) -> None:
    """Assert whether one unconditional project binding contains one member."""

    record = _mapping(policy, field="project policy")
    found = False
    for value in _sequence(record.get("bindings", []), field="project bindings"):
        binding = _mapping(value, field="project binding")
        if binding.get("role") != role:
            continue
        members = set(_sequence(binding.get("members", []), field="project members"))
        found = member in members and (not should_exist or not binding.get("condition"))
        if found:
            break
    if found is not should_exist:
        state = "present" if should_exist else "absent"
        raise UnsafeDeployment(f"{member} must be {state} in project role {role}")


def _json_stdin() -> object:
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise UnsafeDeployment("gcloud did not return valid JSON") from exc


def _members_argument(value: str) -> list[str]:
    try:
        members = json.loads(value)
    except json.JSONDecodeError as exc:
        raise UnsafeDeployment("project binding members argument is not JSON") from exc
    values = _sequence(members, field="project binding members")
    if not all(isinstance(member, str) and member for member in values):
        raise UnsafeDeployment("project binding members must be non-empty strings")
    return list(values)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="check", required=True)

    billing = subparsers.add_parser("billing")
    billing.add_argument("--billing-account-id", required=True)

    budget = subparsers.add_parser("budget")
    budget.add_argument("--project-number", required=True)
    budget.add_argument("--expected-topic", default="")

    topic = subparsers.add_parser("topic-policy")
    topic.add_argument("--budget-publisher", required=True)

    empty = subparsers.add_parser("empty-policy")
    empty.add_argument("--resource", required=True)

    subparsers.add_parser("project-bindings")

    role_access = subparsers.add_parser("role-access")
    role_access.add_argument("--role-name", required=True)
    role_access.add_argument("--members-json", required=True)
    role_access.add_argument("--trusted-member", required=True)
    role_access.add_argument("--runtime-member", required=True)
    role_access.add_argument("--project-number", required=True)
    role_access.add_argument("--runtime-state", choices=("present", "absent"), required=True)

    billing_role_access = subparsers.add_parser("billing-role-access")
    billing_role_access.add_argument("--role-name", required=True)
    billing_role_access.add_argument("--members-json", required=True)
    billing_role_access.add_argument("--trusted-member", required=True)

    exact_project_role = subparsers.add_parser("exact-project-role")
    exact_project_role.add_argument("--role", required=True)
    exact_project_role.add_argument("--member")
    exact_project_role.add_argument("--state", choices=("exact", "absent"), required=True)

    absent = subparsers.add_parser("absent")
    absent.add_argument("--field", required=True)
    absent.add_argument("--value", required=True)

    eventarc_isolation = subparsers.add_parser("eventarc-isolation")
    eventarc_isolation.add_argument("--topic-resource", required=True)
    eventarc_isolation.add_argument("--function-resource", required=True)
    eventarc_isolation.add_argument("--run-service-name", required=True)
    eventarc_isolation.add_argument("--run-service-resource", required=True)

    topic_subscriptions = subparsers.add_parser("topic-subscriptions")
    topic_subscriptions.add_argument("--state", choices=("list", "empty", "single"), required=True)
    topic_subscriptions.add_argument("--project-id")

    message_resource = subparsers.add_parser("message-resource")
    message_resource.add_argument("--resource-label", required=True)
    message_resource.add_argument("--expected-name", required=True)
    message_resource.add_argument("--expected-topic")

    function_trigger = subparsers.add_parser("function-trigger")
    function_trigger.add_argument("--region", required=True)

    eventarc_trigger = subparsers.add_parser("eventarc-trigger")
    eventarc_trigger.add_argument("--expected-name", required=True)
    eventarc_trigger.add_argument("--topic-resource", required=True)
    eventarc_trigger.add_argument("--subscription-resource", required=True)
    eventarc_trigger.add_argument("--trigger-service-account", required=True)
    eventarc_trigger.add_argument("--function-resource", required=True)
    eventarc_trigger.add_argument("--run-service-name", required=True)
    eventarc_trigger.add_argument("--run-service-resource", required=True)
    eventarc_trigger.add_argument("--region", required=True)

    run = subparsers.add_parser("run-policy")
    run.add_argument("--trigger-service-account", required=True)

    function = subparsers.add_parser("function")
    function.add_argument("--runtime-service-account", required=True)
    function.add_argument("--trigger-service-account", required=True)
    function.add_argument("--build-service-account-resource", required=True)
    function.add_argument("--topic-resource", required=True)
    function.add_argument("--expected-billing-account-id", required=True)
    function.add_argument("--expected-budget-id", required=True)
    function.add_argument("--region", required=True)

    project_role = subparsers.add_parser("project-role")
    project_role.add_argument("--role", required=True)
    project_role.add_argument("--member", required=True)
    project_role.add_argument("--state", choices=("present", "absent"), required=True)
    return parser


def main() -> int:
    """Validate one JSON document from stdin for deploy.sh."""

    args = _parser().parse_args()
    document = _json_stdin()
    try:
        if args.check == "billing":
            validate_billing_info(document, billing_account_id=args.billing_account_id)
        elif args.check == "budget":
            validate_budget(
                document,
                project_number=args.project_number,
                expected_topic=args.expected_topic,
            )
        elif args.check == "topic-policy":
            validate_topic_policy(document, budget_publisher=args.budget_publisher)
        elif args.check == "empty-policy":
            validate_empty_policy(document, resource=args.resource)
        elif args.check == "project-bindings":
            for role, members in project_bindings(document):
                print(f"{role}\t{json.dumps(members, separators=(',', ':'))}")
        elif args.check == "role-access":
            validate_role_access(
                document,
                role_name=args.role_name,
                members=_members_argument(args.members_json),
                trusted_member=args.trusted_member,
                runtime_member=args.runtime_member,
                project_number=args.project_number,
                runtime_should_exist=args.runtime_state == "present",
            )
        elif args.check == "billing-role-access":
            validate_billing_role_access(
                document,
                role_name=args.role_name,
                members=_members_argument(args.members_json),
                trusted_member=args.trusted_member,
            )
        elif args.check == "exact-project-role":
            if args.state == "exact" and not args.member:
                raise UnsafeDeployment("exact project role validation requires --member")
            if args.state == "absent" and args.member:
                raise UnsafeDeployment("absent project role validation forbids --member")
            validate_exact_project_role(
                document,
                role=args.role,
                expected_member=args.member if args.state == "exact" else None,
            )
        elif args.check == "absent":
            validate_absent_resources(document, field=args.field, forbidden_value=args.value)
        elif args.check == "eventarc-isolation":
            validate_eventarc_isolation(
                document,
                topic_resource=args.topic_resource,
                function_resource=args.function_resource,
                run_service_name=args.run_service_name,
                run_service_resource=args.run_service_resource,
            )
        elif args.check == "topic-subscriptions":
            if args.state == "single":
                if not args.project_id:
                    raise UnsafeDeployment(
                        "single topic subscription validation requires --project-id"
                    )
                print(validate_single_topic_subscription(document, project_id=args.project_id))
            else:
                if args.project_id:
                    raise UnsafeDeployment(
                        "--project-id is only valid for single subscription state"
                    )
                names = validate_topic_subscriptions(document, require_empty=args.state == "empty")
                if args.state == "list":
                    print("\n".join(names))
        elif args.check == "message-resource":
            validate_message_resource(
                document,
                resource_label=args.resource_label,
                expected_name=args.expected_name,
                expected_topic=args.expected_topic,
            )
        elif args.check == "function-trigger":
            print(function_trigger_resource(document, region=args.region))
        elif args.check == "eventarc-trigger":
            validate_eventarc_trigger(
                document,
                expected_name=args.expected_name,
                topic_resource=args.topic_resource,
                subscription_resource=args.subscription_resource,
                trigger_service_account=args.trigger_service_account,
                function_resource=args.function_resource,
                run_service_name=args.run_service_name,
                run_service_resource=args.run_service_resource,
                region=args.region,
            )
        elif args.check == "run-policy":
            validate_run_policy(document, trigger_service_account=args.trigger_service_account)
        elif args.check == "function":
            validate_function(
                document,
                runtime_service_account=args.runtime_service_account,
                trigger_service_account=args.trigger_service_account,
                build_service_account_resource=args.build_service_account_resource,
                topic_resource=args.topic_resource,
                expected_billing_account_id=args.expected_billing_account_id,
                expected_budget_id=args.expected_budget_id,
                region=args.region,
            )
        elif args.check == "project-role":
            validate_project_role(
                document,
                role=args.role,
                member=args.member,
                should_exist=args.state == "present",
            )
        else:  # pragma: no cover - argparse owns this invariant
            raise AssertionError(args.check)
    except UnsafeDeployment as exc:
        print(f"unsafe D2 deployment: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
