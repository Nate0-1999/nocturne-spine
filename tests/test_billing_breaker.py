"""D2 billing-breaker proofs with fixture messages and no cloud clients."""

import base64
import copy
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BREAKER_DIR = ROOT / "infra" / "billing-breaker"
FIXTURE_DIR = Path(__file__).with_name("fixtures") / "billing_breaker"
MODULE_SPEC = importlib.util.spec_from_file_location(
    "d2_billing_breaker", BREAKER_DIR / "billing_breaker.py"
)
if MODULE_SPEC is None or MODULE_SPEC.loader is None:  # pragma: no cover - import invariant
    raise RuntimeError("unable to load D2 billing-breaker module")
billing_breaker = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = billing_breaker
MODULE_SPEC.loader.exec_module(billing_breaker)

CHECKS_SPEC = importlib.util.spec_from_file_location(
    "d2_deployment_checks", BREAKER_DIR / "deployment_checks.py"
)
if CHECKS_SPEC is None or CHECKS_SPEC.loader is None:  # pragma: no cover
    raise RuntimeError("unable to load D2 deployment checks")
deployment_checks = importlib.util.module_from_spec(CHECKS_SPEC)
sys.modules[CHECKS_SPEC.name] = deployment_checks
CHECKS_SPEC.loader.exec_module(deployment_checks)

ACCOUNT_ID = "01D4EE-079462-DFD6EC"
BUDGET_ID = "de72f49d-779b-4945-a127-4d6ce8def0bb"


@dataclass
class FakeGateway:
    calls: list[tuple[str, str]] = field(default_factory=list)
    billing_account_name: str = "billingAccounts/01D4EE-079462-DFD6EC"
    error: Exception | None = None

    def set_billing_account(self, *, project_name: str, billing_account_name: str) -> None:
        self.calls.append((project_name, billing_account_name))
        if self.error is not None:
            raise self.error
        self.billing_account_name = billing_account_name


@dataclass
class FakeFactory:
    gateway: FakeGateway
    calls: int = 0

    def __call__(self) -> FakeGateway:
        self.calls += 1
        return self.gateway


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text())


def _event(payload: dict[str, Any], **attribute_overrides: str) -> dict[str, Any]:
    attributes = {
        "billingAccountId": ACCOUNT_ID,
        "budgetId": BUDGET_ID,
        "schemaVersion": "1.0",
        **attribute_overrides,
    }
    encoded = base64.b64encode(json.dumps(payload).encode()).decode()
    return {
        "message": {
            "attributes": attributes,
            "data": encoded,
            "messageId": "fixture-message-1",
        },
        "subscription": "projects/n8-memory-palace/subscriptions/fixture",
    }


def _run(
    event: object,
    factory: FakeFactory,
    logs: list[str],
) -> str:
    return billing_breaker.handle_budget_notification(
        event,
        expected_billing_account_id=ACCOUNT_ID,
        expected_budget_id=BUDGET_ID,
        gateway_factory=factory,
        emit=logs.append,
    )


def _records(logs: list[str]) -> list[dict[str, str]]:
    return [json.loads(line) for line in logs]


def _load_main_adapter(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response_billing_enabled: bool,
    response_billing_account_name: str = "",
) -> tuple[ModuleType, Any]:
    class FakeProjectBillingInfo:
        def __init__(self, *, billing_account_name: str) -> None:
            self.billing_account_name = billing_account_name

    class FakeCloudBillingClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def update_project_billing_info(
            self, *, name: str, project_billing_info: FakeProjectBillingInfo
        ) -> SimpleNamespace:
            self.calls.append({"name": name, "project_billing_info": project_billing_info})
            return SimpleNamespace(
                billing_enabled=response_billing_enabled,
                billing_account_name=response_billing_account_name,
            )

    fake_client = FakeCloudBillingClient()
    billing_v1 = ModuleType("google.cloud.billing_v1")
    billing_v1.CloudBillingClient = lambda: fake_client
    billing_v1.ProjectBillingInfo = FakeProjectBillingInfo
    cloud = ModuleType("google.cloud")
    cloud.billing_v1 = billing_v1
    google = ModuleType("google")
    google.cloud = cloud
    framework = ModuleType("functions_framework")
    framework.cloud_event = lambda function: function

    monkeypatch.setitem(sys.modules, "billing_breaker", billing_breaker)
    monkeypatch.setitem(sys.modules, "functions_framework", framework)
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.billing_v1", billing_v1)

    spec = importlib.util.spec_from_file_location(
        "d2_billing_breaker_main", BREAKER_DIR / "main.py"
    )
    if spec is None or spec.loader is None:  # pragma: no cover - import invariant
        raise RuntimeError("unable to load D2 billing-breaker entrypoint")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module, fake_client


def test_below_budget_fixture_never_constructs_gateway() -> None:
    factory = FakeFactory(FakeGateway())
    logs: list[str] = []

    result = _run(_event(_fixture("below_budget")), factory, logs)

    assert result == "below_budget"
    assert factory.calls == 0
    assert factory.gateway.calls == []
    assert _records(logs) == [
        {
            "action": "below_budget",
            "billing_account_id": ACCOUNT_ID,
            "budget_amount": "100.0",
            "budget_id": BUDGET_ID,
            "component": "billing-breaker",
            "cost_amount": "99.99",
            "message_id": "fixture-message-1",
            "project_id": "n8-memory-palace",
            "severity": "INFO",
        }
    ]


@pytest.mark.parametrize("fixture_name", ["at_budget", "above_budget"])
def test_equality_and_overage_detach_the_fixed_project(fixture_name: str) -> None:
    factory = FakeFactory(FakeGateway())
    logs: list[str] = []

    result = _run(_event(_fixture(fixture_name)), factory, logs)

    assert result == "billing_detached"
    assert factory.calls == 1
    assert factory.gateway.calls == [("projects/n8-memory-palace", "")]
    assert factory.gateway.billing_account_name == ""
    records = _records(logs)
    assert [record["action"] for record in records] == [
        "detach_requested",
        "billing_detached",
    ]
    assert all(record["project_id"] == "n8-memory-palace" for record in records)


def test_duplicate_delivery_repeats_the_same_idempotent_desired_state() -> None:
    gateway = FakeGateway()
    factory = FakeFactory(gateway)
    event = _event(_fixture("at_budget"))
    logs: list[str] = []

    assert _run(event, factory, logs) == "billing_detached"
    assert _run(event, factory, logs) == "billing_detached"

    assert gateway.billing_account_name == ""
    assert gateway.calls == [
        ("projects/n8-memory-palace", ""),
        ("projects/n8-memory-palace", ""),
    ]
    assert [record["action"] for record in _records(logs)] == [
        "detach_requested",
        "billing_detached",
        "detach_requested",
        "billing_detached",
    ]


@pytest.mark.parametrize(
    ("event", "reason"),
    [
        ({}, "message_missing"),
        (
            {"message": {"attributes": {}, "data": "%%%", "messageId": "bad"}},
            "schema_version_mismatch",
        ),
        (_event(_fixture("at_budget"), schemaVersion="2.0"), "schema_version_mismatch"),
        (_event(_fixture("at_budget"), billingAccountId="other"), "billing_account_mismatch"),
        (_event(_fixture("at_budget"), budgetId="other"), "budget_id_mismatch"),
        (_event({**_fixture("at_budget"), "costAmount": True}), "invalid_cost_amount"),
        (_event({**_fixture("at_budget"), "budgetAmount": 0}), "invalid_budget_amount"),
        (_event({**_fixture("at_budget"), "currencyCode": "EUR"}), "currency_mismatch"),
    ],
)
def test_invalid_or_foreign_notifications_are_logged_and_acknowledged(
    event: object, reason: str
) -> None:
    factory = FakeFactory(FakeGateway())
    logs: list[str] = []

    result = _run(event, factory, logs)

    assert result == "invalid_notification"
    assert factory.calls == 0
    assert factory.gateway.calls == []
    assert _records(logs)[0]["action"] == "invalid_notification"
    assert _records(logs)[0]["reason"] == reason


def test_malformed_base64_and_json_never_reach_the_gateway() -> None:
    factory = FakeFactory(FakeGateway())
    attributes = {
        "billingAccountId": ACCOUNT_ID,
        "budgetId": BUDGET_ID,
        "schemaVersion": "1.0",
    }
    events = [
        {"message": {"attributes": attributes, "data": "%%%", "messageId": "bad-1"}},
        {
            "message": {
                "attributes": attributes,
                "data": base64.b64encode(b"not json").decode(),
                "messageId": "bad-2",
            }
        },
    ]

    reasons = []
    for event in events:
        logs: list[str] = []
        assert _run(event, factory, logs) == "invalid_notification"
        reasons.append(_records(logs)[0]["reason"])

    assert reasons == ["message_data_not_base64_utf8", "message_data_not_json"]
    assert factory.calls == 0


def test_billing_api_failure_is_logged_and_propagated() -> None:
    gateway = FakeGateway(error=PermissionError("fixture denial"))
    factory = FakeFactory(gateway)
    logs: list[str] = []

    with pytest.raises(PermissionError, match="fixture denial"):
        _run(_event(_fixture("at_budget")), factory, logs)

    records = _records(logs)
    assert [record["action"] for record in records] == ["detach_requested", "detach_failed"]
    assert records[-1]["error_type"] == "PermissionError"
    assert "fixture denial" not in logs[-1]


def test_cloud_event_entrypoint_builds_the_exact_sdk_detach_request(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    main, fake_client = _load_main_adapter(monkeypatch, response_billing_enabled=False)
    monkeypatch.setenv("EXPECTED_BILLING_ACCOUNT_ID", ACCOUNT_ID)
    monkeypatch.setenv("EXPECTED_BUDGET_ID", BUDGET_ID)

    main.stop_billing(SimpleNamespace(data=_event(_fixture("at_budget"))))

    assert len(fake_client.calls) == 1
    request = fake_client.calls[0]
    assert request["name"] == "projects/n8-memory-palace"
    assert request["project_billing_info"].billing_account_name == ""
    assert [json.loads(line)["action"] for line in capsys.readouterr().out.splitlines()] == [
        "detach_requested",
        "billing_detached",
    ]


@pytest.mark.parametrize(
    ("billing_enabled", "billing_account_name"),
    [(True, ""), (False, f"billingAccounts/{ACCOUNT_ID}")],
)
def test_cloud_event_entrypoint_rejects_an_unconfirmed_postcondition(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    billing_enabled: bool,
    billing_account_name: str,
) -> None:
    main, fake_client = _load_main_adapter(
        monkeypatch,
        response_billing_enabled=billing_enabled,
        response_billing_account_name=billing_account_name,
    )
    monkeypatch.setenv("EXPECTED_BILLING_ACCOUNT_ID", ACCOUNT_ID)
    monkeypatch.setenv("EXPECTED_BUDGET_ID", BUDGET_ID)

    with pytest.raises(RuntimeError, match="did not confirm the empty billing assignment"):
        main.stop_billing(SimpleNamespace(data=_event(_fixture("above_budget"))))

    assert len(fake_client.calls) == 1
    records = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [record["action"] for record in records] == ["detach_requested", "detach_failed"]
    assert records[-1]["error_type"] == "RuntimeError"


def test_deploy_script_is_default_inert_and_least_privileged() -> None:
    subprocess.run(["bash", "-n", str(BREAKER_DIR / "deploy.sh")], check=True)
    script = (BREAKER_DIR / "deploy.sh").read_text()

    for token in (
        "n8-memory-palace",
        "billing-breaker",
        "python312",
        "--trigger-topic=${TOPIC_ID}",
        "--run-service-account=${RUNTIME_SA_EMAIL}",
        "--trigger-service-account=${TRIGGER_SA_EMAIL}",
        "--build-service-account=${BUILD_SA_RESOURCE}",
        "--no-retry",
        "gcloud functions list",
        "gcloud run services list",
        "gcloud eventarc triggers list",
        "gcloud eventarc triggers describe",
        "gcloud pubsub topics describe",
        "gcloud pubsub topics list-subscriptions",
        "gcloud pubsub subscriptions describe",
        "gcloud pubsub subscriptions get-iam-policy",
        "gcloud iam service-accounts get-iam-policy",
        "gcloud billing accounts get-iam-policy",
        "gcloud iam roles describe",
        "project-bindings",
        "role-access",
        "billing-role-access",
        "exact-project-role",
        "eventarc-isolation",
        "function-trigger",
        "eventarc-trigger",
        "message-resource",
        "--state single",
        "auth/impersonate_service_account",
        "auth/access_token_file",
        "auth/credential_file_override",
        "billing.accounts.setIamPolicy",
        "billing.budgets.update",
        "billing.resourcebudgets.write",
        "roles/billing.projectManager",
        "run services add-iam-policy-binding ${FUNCTION_NAME}",
        "--notifications-rule-pubsub-topic=${TOPIC_RESOURCE}",
    ):
        assert token in script
    assert script.index('if [[ "$MODE" == "--dry-run" ]]') < script.index("command -v gcloud")
    assert script.index("if [[ ! -t 0 || ! -t 1 ]]") < script.index("command -v gcloud")
    active_account_check = script.index('active_account="$(gcloud auth list')
    for auth_property in (
        "auth/impersonate_service_account",
        "auth/access_token_file",
        "auth/credential_file_override",
    ):
        assert script.index(auth_property) < active_account_check
    assert "billing accounts add-iam-policy-binding" not in script
    assert "--role=roles/eventarc.eventReceiver" not in script
    assert "--role=roles/artifactregistry.reader" not in script
    assert "eventarcpublishing.googleapis.com" not in script
    assert "require_absent" not in script
    assert "failed safely" not in script
    assert "\n    --retry \\" not in script
    grant_log = script.index(
        'log "granting project-scoped detach authority immediately before budget wiring"'
    )
    assert script.index("detach_cleanup_required=1", grant_log) < script.index(
        'gcloud projects add-iam-policy-binding "$PROJECT_ID"', grant_log
    )
    build_log = script.index(
        'log "granting the documented build roles to the isolated build identity"'
    )
    assert script.index("build_cleanup_required=1", build_log) < script.index(
        'gcloud projects add-iam-policy-binding "$PROJECT_ID"', build_log
    )
    for signal in ("ERR", "EXIT", "INT", "TERM", "HUP"):
        assert f"trap 'rollback_on_error {signal}' {signal}" in script
    assert (
        "projects add-iam-policy-binding n8-memory-palace --project=n8-memory-palace "
        "--member=serviceAccount:billing-breaker-trigger@"
        "n8-memory-palace.iam.gserviceaccount.com "
        "--role=roles/run.invoker"
    ) not in script


def test_runbook_proves_subscription_and_resource_absence_from_lists() -> None:
    runbook = (BREAKER_DIR / "README.md").read_text()
    recovery = runbook.split("## Recovery and billing reattach", maxsplit=1)[1]

    for token in (
        'pubsub = trigger.get("transport", {}).get("pubsub", {})',
        "print(name)",
        "gcloud pubsub subscriptions delete",
        "gcloud pubsub topics detach-subscription",
        "gcloud pubsub topics list-subscriptions",
        "gcloud functions list --v2",
        "gcloud run services list",
        "gcloud pubsub topics list",
        "gcloud iam service-accounts list",
        "deployment_checks.py absent",
        "deployment_checks.py exact-project-role",
        "deployment_checks.py topic-subscriptions --state=list",
        "deployment_checks.py topic-subscriptions --state=empty",
    ):
        assert token in runbook
    assert runbook.index("subscription_before_json") < runbook.index(
        "gcloud functions delete billing-breaker"
    )
    assert "expect_not_found" not in runbook
    assert 'test -z "$(gcloud' not in runbook
    assert 'if ! subscription_rows="$(' in recovery
    assert recovery.count("python3 deployment_checks.py") == (
        recovery.count("if ! printf '%s'") + 1
    )


def _budget(*, topic: str = "") -> dict[str, Any]:
    notifications_rule = {"pubsubTopic": topic, "schemaVersion": "1.0"} if topic else {}
    return {
        "amount": {
            "specifiedAmount": {
                "currencyCode": "USD",
                "nanos": 0,
                "units": "100",
            }
        },
        "budgetFilter": {
            "calendarPeriod": "MONTH",
            "creditTypesTreatment": "INCLUDE_ALL_CREDITS",
            "projects": ["projects/123456789"],
        },
        "notificationsRule": notifications_rule,
        "ownershipScope": "BILLING_ACCOUNT",
    }


def test_deploy_budget_validator_accepts_only_disconnected_or_exact_armed_phase() -> None:
    topic = "projects/n8-memory-palace/topics/billing-breaker"

    deployment_checks.validate_budget(_budget(), project_number="123456789", expected_topic="")
    disconnected_with_retained_schema = _budget()
    disconnected_with_retained_schema["notificationsRule"] = {"schemaVersion": "1.0"}
    deployment_checks.validate_budget(
        disconnected_with_retained_schema,
        project_number="123456789",
        expected_topic="",
    )
    deployment_checks.validate_budget(
        _budget(topic=topic), project_number="123456789", expected_topic=topic
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("calendarPeriod", "YEAR"),
        ("creditTypes", ["PROMOTION"]),
        ("creditTypesTreatment", "EXCLUDE_ALL_CREDITS"),
        ("customPeriod", {"startDate": {"year": 2026}}),
        ("labels", {"env": {"values": ["prod"]}}),
        ("resourceAncestors", ["organizations/123"]),
        ("services", ["services/abc"]),
        ("subaccounts", ["billingAccounts/child"]),
    ],
)
def test_deploy_budget_validator_rejects_narrowing_filters(field: str, value: object) -> None:
    budget = copy.deepcopy(_budget())
    budget["budgetFilter"][field] = value

    with pytest.raises(deployment_checks.UnsafeDeployment):
        deployment_checks.validate_budget(budget, project_number="123456789", expected_topic="")


def test_deploy_budget_validator_rejects_extra_project_and_wrong_topic() -> None:
    budget = _budget()
    budget["budgetFilter"]["projects"].append("projects/987654321")

    with pytest.raises(deployment_checks.UnsafeDeployment, match="projects must be exactly"):
        deployment_checks.validate_budget(budget, project_number="123456789", expected_topic="")
    with pytest.raises(deployment_checks.UnsafeDeployment, match="deployment phase"):
        deployment_checks.validate_budget(
            _budget(topic="projects/other/topics/wrong"),
            project_number="123456789",
            expected_topic="projects/n8-memory-palace/topics/billing-breaker",
        )


def test_deploy_budget_validator_requires_billing_account_ownership() -> None:
    budget = _budget()
    budget["ownershipScope"] = "ALL_USERS"

    with pytest.raises(deployment_checks.UnsafeDeployment, match="ownershipScope"):
        deployment_checks.validate_budget(
            budget,
            project_number="123456789",
            expected_topic="",
        )


def test_deploy_topic_policy_allows_only_the_budget_publisher() -> None:
    policy = {
        "bindings": [
            {
                "members": ["serviceAccount:billing-budget-alert@system.gserviceaccount.com"],
                "role": "roles/pubsub.publisher",
            }
        ]
    }

    deployment_checks.validate_topic_policy(
        policy, budget_publisher="billing-budget-alert@system.gserviceaccount.com"
    )
    policy["bindings"][0]["members"].append("user:untrusted@example.com")
    with pytest.raises(deployment_checks.UnsafeDeployment):
        deployment_checks.validate_topic_policy(
            policy, budget_publisher="billing-budget-alert@system.gserviceaccount.com"
        )


@pytest.mark.parametrize(
    ("role_name", "permission"),
    [
        ("roles/cloudbuild.builds.builder", "pubsub.topics.publish"),
        ("roles/firebaserules.system", "pubsub.topics.publish"),
        ("roles/composer.worker", "pubsub.topics.publish"),
        ("roles/storagetransfer.transferAgent", "pubsub.topics.publish"),
        ("roles/pubsub.editor", "pubsub.topics.attachSubscription"),
        ("projects/n8-memory-palace/roles/detacher", "pubsub.topics.detachSubscription"),
        ("roles/pubsub.editor", "pubsub.topics.update"),
        ("roles/pubsub.editor", "pubsub.subscriptions.update"),
        ("roles/pubsub.admin", "pubsub.subscriptions.setIamPolicy"),
        ("roles/cloudfunctions.developer", "cloudfunctions.functions.update"),
        ("projects/n8-memory-palace/roles/eventarcIam", "eventarc.triggers.setIamPolicy"),
        ("roles/eventarc.developer", "eventarc.triggers.update"),
        ("roles/run.developer", "run.services.update"),
        ("roles/iam.securityAdmin", "resourcemanager.projects.setIamPolicy"),
        ("roles/iam.admin", "iam.serviceAccounts.actAs"),
        ("roles/billing.admin", "billing.accounts.setIamPolicy"),
        ("roles/billing.costsManager", "billing.budgets.update"),
        ("roles/editor", "billing.resourcebudgets.write"),
        ("roles/resourcemanager.projectIamAdmin", "resourcemanager.projects.setIamPolicy"),
        ("roles/cloudfunctions.serviceAgent", "run.routes.invoke"),
        ("roles/run.serviceAgent", "iam.serviceAccounts.getOpenIdToken"),
        (
            "roles/billing.projectManager",
            "resourcemanager.projects.createBillingAssignment",
        ),
        (
            "projects/n8-memory-palace/roles/customBillingDetach",
            "resourcemanager.projects.deleteBillingAssignment",
        ),
    ],
)
def test_deploy_role_permissions_reject_untrusted_destructive_access(
    role_name: str, permission: str
) -> None:
    trusted = "user:deployer@example.com"
    runtime = "serviceAccount:billing-breaker-runtime@n8-memory-palace.iam.gserviceaccount.com"
    role = {"includedPermissions": [permission], "name": role_name}

    deployment_checks.validate_role_access(
        role,
        role_name=role_name,
        members=[trusted],
        trusted_member=trusted,
        runtime_member=runtime,
        project_number="123456789",
        runtime_should_exist=False,
    )

    with pytest.raises(deployment_checks.UnsafeDeployment, match="breaker permissions"):
        deployment_checks.validate_role_access(
            role,
            role_name=role_name,
            members=["serviceAccount:untrusted@example.com"],
            trusted_member=trusted,
            runtime_member=runtime,
            project_number="123456789",
            runtime_should_exist=False,
        )


def test_deploy_role_permissions_allow_only_current_project_service_agents() -> None:
    role_name = "roles/cloudfunctions.serviceAgent"
    role = {"includedPermissions": ["run.routes.invoke"], "name": role_name}
    common = {
        "role_name": role_name,
        "trusted_member": "user:deployer@example.com",
        "runtime_member": (
            "serviceAccount:billing-breaker-runtime@n8-memory-palace.iam.gserviceaccount.com"
        ),
        "project_number": "123456789",
        "runtime_should_exist": False,
    }
    deployment_checks.validate_role_access(
        role,
        members=["serviceAccount:service-123456789@gcf-admin-robot.iam.gserviceaccount.com"],
        **common,
    )
    # Google default identities present in essentially every project must not
    # block a default-posture deployment: the Container Registry service agent,
    # a reserved gcp-sa-* per-service agent, and the default Compute Engine SA.
    for default_member in (
        "serviceAccount:service-123456789@containerregistry.iam.gserviceaccount.com",
        "serviceAccount:service-123456789@gcp-sa-run.iam.gserviceaccount.com",
        "serviceAccount:123456789-compute@developer.gserviceaccount.com",
        "serviceAccount:n8-memory-palace@appspot.gserviceaccount.com",
    ):
        deployment_checks.validate_role_access(role, members=[default_member], **common)

    with pytest.raises(deployment_checks.UnsafeDeployment, match="breaker permissions"):
        deployment_checks.validate_role_access(
            role,
            members=["serviceAccount:service-987654321@gcf-admin-robot.iam.gserviceaccount.com"],
            **common,
        )
    with pytest.raises(deployment_checks.UnsafeDeployment, match="breaker permissions"):
        deployment_checks.validate_role_access(
            role,
            members=["serviceAccount:service-123456789@attacker-project.iam.gserviceaccount.com"],
            **common,
        )

    # A Google service agent whose role carries project-level billing CONTROL
    # (budget write) is allowed: the breaker budget is BILLING_ACCOUNT-scoped and
    # cannot be modified by a project principal, so this is inert here.
    deployment_checks.validate_role_access(
        {"includedPermissions": ["billing.budgets.update"], "name": role_name},
        members=["serviceAccount:service-123456789@gcf-admin-robot.iam.gserviceaccount.com"],
        **common,
    )
    # But direct billing ASSOCIATION (project-level detach) on any non-runtime
    # identity — even a Google service agent — is still refused.
    with pytest.raises(deployment_checks.UnsafeDeployment, match="breaker permissions"):
        deployment_checks.validate_role_access(
            {
                "includedPermissions": ["resourcemanager.projects.deleteBillingAssignment"],
                "name": role_name,
            },
            members=["serviceAccount:service-123456789@gcf-admin-robot.iam.gserviceaccount.com"],
            **common,
        )


def test_deploy_billing_role_and_public_members_are_exact() -> None:
    trusted = "user:deployer@example.com"
    runtime = "serviceAccount:billing-breaker-runtime@n8-memory-palace.iam.gserviceaccount.com"
    billing_role = {
        "includedPermissions": ["resourcemanager.projects.createBillingAssignment"],
        "name": "roles/billing.projectManager",
    }
    common = {
        "role_name": "roles/billing.projectManager",
        "trusted_member": trusted,
        "runtime_member": runtime,
        "project_number": "123456789",
    }
    deployment_checks.validate_role_access(
        billing_role, members=[runtime], runtime_should_exist=True, **common
    )
    with pytest.raises(deployment_checks.UnsafeDeployment, match="breaker permissions"):
        deployment_checks.validate_role_access(
            billing_role, members=[runtime], runtime_should_exist=False, **common
        )
    for extra_permission in ("billing.budgets.update", "pubsub.topics.publish"):
        drifted_role = copy.deepcopy(billing_role)
        drifted_role["includedPermissions"].append(extra_permission)
        with pytest.raises(deployment_checks.UnsafeDeployment, match="breaker permissions"):
            deployment_checks.validate_role_access(
                drifted_role,
                members=[runtime],
                runtime_should_exist=True,
                **common,
            )
    with pytest.raises(deployment_checks.UnsafeDeployment, match="public project"):
        deployment_checks.validate_role_access(
            {"includedPermissions": [], "name": "roles/viewer"},
            role_name="roles/viewer",
            members=["allUsers"],
            trusted_member=trusted,
            runtime_member=runtime,
            project_number="123456789",
            runtime_should_exist=False,
        )


@pytest.mark.parametrize(
    ("role_name", "permission"),
    [
        ("roles/billing.admin", "billing.accounts.close"),
        ("roles/billing.admin", "billing.accounts.setIamPolicy"),
        ("roles/billing.costsManager", "billing.budgets.update"),
        (
            "organizations/123/roles/customAccountDetach",
            "billing.resourceAssociations.delete",
        ),
        ("roles/editor", "billing.resourcebudgets.write"),
    ],
)
def test_deploy_billing_account_control_is_human_only(role_name: str, permission: str) -> None:
    trusted = "user:deployer@example.com"
    role = {"includedPermissions": [permission], "name": role_name}

    deployment_checks.validate_billing_role_access(
        role,
        role_name=role_name,
        members=[trusted],
        trusted_member=trusted,
    )
    with pytest.raises(deployment_checks.UnsafeDeployment, match="billing-account members"):
        deployment_checks.validate_billing_role_access(
            role,
            role_name=role_name,
            members=["group:billing-admins@example.com"],
            trusted_member=trusted,
        )


def test_deploy_project_bindings_and_billing_manager_membership_are_exact() -> None:
    runtime = "serviceAccount:billing-breaker-runtime@n8-memory-palace.iam.gserviceaccount.com"
    empty_policy = {"bindings": [{"members": ["user:a@example.com"], "role": "roles/viewer"}]}
    assert deployment_checks.project_bindings(empty_policy) == [
        ("roles/viewer", ["user:a@example.com"])
    ]
    deployment_checks.validate_exact_project_role(
        empty_policy, role="roles/billing.projectManager", expected_member=None
    )

    exact_policy = {
        "bindings": [
            {
                "members": [runtime],
                "role": "roles/billing.projectManager",
            }
        ]
    }
    deployment_checks.validate_exact_project_role(
        exact_policy,
        role="roles/billing.projectManager",
        expected_member=runtime,
    )
    for unsafe_policy in (
        {
            "bindings": [
                {
                    "members": [runtime, "user:other@example.com"],
                    "role": "roles/billing.projectManager",
                }
            ]
        },
        {
            "bindings": [
                {
                    "condition": {"expression": "request.time < timestamp('2030-01-01T00:00:00Z')"},
                    "members": [runtime],
                    "role": "roles/billing.projectManager",
                }
            ]
        },
    ):
        with pytest.raises(deployment_checks.UnsafeDeployment):
            deployment_checks.validate_exact_project_role(
                unsafe_policy,
                role="roles/billing.projectManager",
                expected_member=runtime,
            )


def test_deploy_resource_absence_uses_successful_exact_list_results() -> None:
    deployment_checks.validate_absent_resources(
        [{"name": "projects/n8-memory-palace/topics/other"}],
        field="name",
        forbidden_value="projects/n8-memory-palace/topics/billing-breaker",
    )
    deployment_checks.validate_absent_resources(
        [{"metadata": {"name": "other"}}],
        field="metadata.name",
        forbidden_value="billing-breaker",
    )

    with pytest.raises(deployment_checks.UnsafeDeployment, match="fresh deployment"):
        deployment_checks.validate_absent_resources(
            [{"metadata": {"name": "billing-breaker"}}],
            field="metadata.name",
            forbidden_value="billing-breaker",
        )


def test_deploy_topic_subscription_list_includes_cross_project_names() -> None:
    expected = [
        "projects/attacker-project/subscriptions/retained",
        "projects/n8-memory-palace/subscriptions/eventarc-managed",
    ]
    assert (
        deployment_checks.topic_subscription_names({"subscriptions": list(reversed(expected))})
        == expected
    )
    assert (
        deployment_checks.topic_subscription_names([{"name": name} for name in reversed(expected)])
        == expected
    )
    assert deployment_checks.validate_topic_subscriptions([], require_empty=True) == []
    with pytest.raises(deployment_checks.UnsafeDeployment, match="still has attached"):
        deployment_checks.validate_topic_subscriptions(expected, require_empty=True)
    assert (
        deployment_checks.validate_single_topic_subscription(
            [expected[1]], project_id="n8-memory-palace"
        )
        == expected[1]
    )
    with pytest.raises(deployment_checks.UnsafeDeployment, match="exactly one"):
        deployment_checks.validate_single_topic_subscription(
            expected, project_id="n8-memory-palace"
        )

    with pytest.raises(deployment_checks.UnsafeDeployment, match="malformed"):
        deployment_checks.topic_subscription_names(
            ["projects/n8-memory-palace/topics/not-a-subscription"]
        )


def test_deploy_message_path_resources_forbid_single_message_transforms() -> None:
    topic = "projects/n8-memory-palace/topics/billing-breaker"
    subscription = "projects/n8-memory-palace/subscriptions/eventarc-managed"
    deployment_checks.validate_message_resource(
        {"name": topic},
        resource_label="D2 topic",
        expected_name=topic,
    )
    deployment_checks.validate_message_resource(
        {"messageTransforms": [], "name": subscription, "topic": topic},
        resource_label="D2 Eventarc subscription",
        expected_name=subscription,
        expected_topic=topic,
    )

    with pytest.raises(deployment_checks.UnsafeDeployment, match="message transforms"):
        deployment_checks.validate_message_resource(
            {
                "messageTransforms": [{"javascriptUdf": {"code": "return message;"}}],
                "name": subscription,
                "topic": topic,
            },
            resource_label="D2 Eventarc subscription",
            expected_name=subscription,
            expected_topic=topic,
        )


@pytest.mark.parametrize(
    "trigger",
    [
        {
            "name": "projects/n8-memory-palace/locations/us-central1/triggers/old-topic",
            "transport": {"pubsub": {"topic": "projects/n8-memory-palace/topics/billing-breaker"}},
        },
        {
            "destination": {
                "cloudFunction": (
                    "projects/n8-memory-palace/locations/us-central1/functions/billing-breaker"
                )
            },
            "name": "projects/n8-memory-palace/locations/us-central1/triggers/old-function",
        },
        {
            "destination": {"cloudRun": {"service": "billing-breaker"}},
            "name": "projects/n8-memory-palace/locations/us-central1/triggers/old-service",
        },
    ],
)
def test_deploy_rejects_old_eventarc_paths_to_fresh_d2_names(
    trigger: dict[str, Any],
) -> None:
    common = {
        "topic_resource": "projects/n8-memory-palace/topics/billing-breaker",
        "function_resource": (
            "projects/n8-memory-palace/locations/us-central1/functions/billing-breaker"
        ),
        "run_service_name": "billing-breaker",
        "run_service_resource": (
            "projects/n8-memory-palace/locations/us-central1/services/billing-breaker"
        ),
    }
    deployment_checks.validate_eventarc_isolation(
        [
            {
                "destination": {"cloudRun": {"service": "unrelated"}},
                "name": "projects/n8-memory-palace/locations/us-central1/triggers/unrelated",
                "transport": {"pubsub": {"topic": "projects/n8-memory-palace/topics/unrelated"}},
            }
        ],
        **common,
    )
    with pytest.raises(deployment_checks.UnsafeDeployment, match="reconnect"):
        deployment_checks.validate_eventarc_isolation([trigger], **common)


def test_deploy_service_account_policy_must_be_empty() -> None:
    deployment_checks.validate_empty_policy({}, resource="runtime service account")

    with pytest.raises(deployment_checks.UnsafeDeployment, match="direct IAM"):
        deployment_checks.validate_empty_policy(
            {
                "bindings": [
                    {
                        "members": ["user:impersonator@example.com"],
                        "role": "roles/iam.serviceAccountTokenCreator",
                    }
                ]
            },
            resource="runtime service account",
        )


def test_deploy_function_and_run_policy_pin_all_identities() -> None:
    runtime = "billing-breaker-runtime@n8-memory-palace.iam.gserviceaccount.com"
    trigger = "billing-breaker-trigger@n8-memory-palace.iam.gserviceaccount.com"
    build = (
        "projects/n8-memory-palace/serviceAccounts/"
        "billing-breaker-build@n8-memory-palace.iam.gserviceaccount.com"
    )
    topic = "projects/n8-memory-palace/topics/billing-breaker"
    function = {
        "buildConfig": {
            "entryPoint": "stop_billing",
            "runtime": "python312",
            "serviceAccount": build,
        },
        "environment": "GEN_2",
        "eventTrigger": {
            "eventType": "google.cloud.pubsub.topic.v1.messagePublished",
            "pubsubTopic": topic,
            "retryPolicy": "RETRY_POLICY_DO_NOT_RETRY",
            "serviceAccountEmail": trigger,
            "trigger": (
                "projects/n8-memory-palace/locations/us-central1/triggers/billing-breaker-123456"
            ),
            "triggerRegion": "us-central1",
        },
        "serviceConfig": {
            "environmentVariables": {
                "EXPECTED_BILLING_ACCOUNT_ID": ACCOUNT_ID,
                "EXPECTED_BUDGET_ID": BUDGET_ID,
            },
            "serviceAccountEmail": runtime,
        },
        "state": "ACTIVE",
    }

    deployment_checks.validate_function(
        function,
        runtime_service_account=runtime,
        trigger_service_account=trigger,
        build_service_account_resource=build,
        topic_resource=topic,
        expected_billing_account_id=ACCOUNT_ID,
        expected_budget_id=BUDGET_ID,
        region="us-central1",
    )
    trigger_resource = deployment_checks.function_trigger_resource(function, region="us-central1")
    subscription_resource = "projects/n8-memory-palace/subscriptions/eventarc-managed"
    eventarc_trigger = {
        "conditions": {},
        "destination": {"cloudRun": {"region": "us-central1", "service": "billing-breaker"}},
        "eventFilters": [
            {
                "attribute": "type",
                "value": "google.cloud.pubsub.topic.v1.messagePublished",
            }
        ],
        "name": trigger_resource,
        "serviceAccount": trigger,
        "transport": {
            "pubsub": {
                "subscription": subscription_resource,
                "topic": topic,
            }
        },
    }
    eventarc_common = {
        "expected_name": trigger_resource,
        "topic_resource": topic,
        "subscription_resource": subscription_resource,
        "trigger_service_account": trigger,
        "function_resource": (
            "projects/n8-memory-palace/locations/us-central1/functions/billing-breaker"
        ),
        "run_service_name": "billing-breaker",
        "run_service_resource": (
            "projects/n8-memory-palace/locations/us-central1/services/billing-breaker"
        ),
        "region": "us-central1",
    }
    deployment_checks.validate_eventarc_trigger(eventarc_trigger, **eventarc_common)
    for path, value, message in (
        (
            ("transport", "pubsub", "subscription"),
            "projects/other/subscriptions/rogue",
            "subscription",
        ),
        (("destination", "cloudRun", "path"), "/rogue", "destination path"),
        (("conditions",), {"transport": {"code": "FAILED_PRECONDITION"}}, "not healthy"),
    ):
        unsafe_trigger = copy.deepcopy(eventarc_trigger)
        target = unsafe_trigger
        for part in path[:-1]:
            target = target[part]
        target[path[-1]] = value
        with pytest.raises(deployment_checks.UnsafeDeployment, match=message):
            deployment_checks.validate_eventarc_trigger(unsafe_trigger, **eventarc_common)
    deployment_checks.validate_run_policy(
        {
            "bindings": [
                {
                    "members": [f"serviceAccount:{trigger}"],
                    "role": "roles/run.invoker",
                }
            ]
        },
        trigger_service_account=trigger,
    )

    function["eventTrigger"]["retryPolicy"] = "RETRY_POLICY_RETRY"
    with pytest.raises(deployment_checks.UnsafeDeployment, match="retryPolicy"):
        deployment_checks.validate_function(
            function,
            runtime_service_account=runtime,
            trigger_service_account=trigger,
            build_service_account_resource=build,
            topic_resource=topic,
            expected_billing_account_id=ACCOUNT_ID,
            expected_budget_id=BUDGET_ID,
            region="us-central1",
        )


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (("environment",), "GEN_1", "environment"),
        (("buildConfig", "runtime"), "python311", "runtime"),
        (("buildConfig", "entryPoint"), "other", "entry point"),
        (
            ("serviceConfig", "environmentVariables", "EXPECTED_BUDGET_ID"),
            "wrong",
            "EXPECTED_BUDGET_ID",
        ),
        (("eventTrigger", "triggerRegion"), "us-east1", "triggerRegion"),
    ],
)
def test_deploy_function_rejects_wrong_runtime_or_identity_configuration(
    path: tuple[str, ...], value: str, message: str
) -> None:
    runtime = "billing-breaker-runtime@n8-memory-palace.iam.gserviceaccount.com"
    trigger = "billing-breaker-trigger@n8-memory-palace.iam.gserviceaccount.com"
    build = (
        "projects/n8-memory-palace/serviceAccounts/"
        "billing-breaker-build@n8-memory-palace.iam.gserviceaccount.com"
    )
    topic = "projects/n8-memory-palace/topics/billing-breaker"
    function: dict[str, Any] = {
        "buildConfig": {
            "entryPoint": "stop_billing",
            "runtime": "python312",
            "serviceAccount": build,
        },
        "environment": "GEN_2",
        "eventTrigger": {
            "eventType": "google.cloud.pubsub.topic.v1.messagePublished",
            "pubsubTopic": topic,
            "retryPolicy": "RETRY_POLICY_DO_NOT_RETRY",
            "serviceAccountEmail": trigger,
            "trigger": (
                "projects/n8-memory-palace/locations/us-central1/triggers/billing-breaker-123456"
            ),
            "triggerRegion": "us-central1",
        },
        "serviceConfig": {
            "environmentVariables": {
                "EXPECTED_BILLING_ACCOUNT_ID": ACCOUNT_ID,
                "EXPECTED_BUDGET_ID": BUDGET_ID,
            },
            "serviceAccountEmail": runtime,
        },
        "state": "ACTIVE",
    }
    target: dict[str, Any] = function
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value

    with pytest.raises(deployment_checks.UnsafeDeployment, match=message):
        deployment_checks.validate_function(
            function,
            runtime_service_account=runtime,
            trigger_service_account=trigger,
            build_service_account_resource=build,
            topic_resource=topic,
            expected_billing_account_id=ACCOUNT_ID,
            expected_budget_id=BUDGET_ID,
            region="us-central1",
        )


def test_deploy_run_policy_rejects_public_or_extra_invokers() -> None:
    trigger = "billing-breaker-trigger@n8-memory-palace.iam.gserviceaccount.com"
    for member in ("allUsers", "user:other@example.com"):
        policy = {
            "bindings": [
                {
                    "members": [f"serviceAccount:{trigger}", member],
                    "role": "roles/run.invoker",
                }
            ]
        }
        with pytest.raises(deployment_checks.UnsafeDeployment):
            deployment_checks.validate_run_policy(policy, trigger_service_account=trigger)

    for extra in (
        {"condition": {"expression": "request.time < timestamp('2020-01-01T00:00:00Z')"}},
        {
            "extra_binding": {
                "members": ["user:admin@example.com"],
                "role": "roles/run.admin",
            }
        },
    ):
        binding = {
            "members": [f"serviceAccount:{trigger}"],
            "role": "roles/run.invoker",
        }
        if "condition" in extra:
            binding["condition"] = extra["condition"]
        bindings = [binding]
        if "extra_binding" in extra:
            bindings.append(extra["extra_binding"])
        with pytest.raises(deployment_checks.UnsafeDeployment):
            deployment_checks.validate_run_policy(
                {"bindings": bindings}, trigger_service_account=trigger
            )
