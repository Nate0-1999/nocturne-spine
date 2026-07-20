"""Cloud Run function adapter for the billing circuit breaker."""

import os

import functions_framework
from billing_breaker import handle_budget_notification


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value


class GoogleBillingGateway:
    """Cloud Billing API adapter kept outside the pure decision engine."""

    def __init__(self) -> None:
        from google.cloud import billing_v1

        self._billing_v1 = billing_v1
        self._client = billing_v1.CloudBillingClient()

    def set_billing_account(self, *, project_name: str, billing_account_name: str) -> None:
        project_billing_info = self._billing_v1.ProjectBillingInfo(
            billing_account_name=billing_account_name
        )
        response = self._client.update_project_billing_info(
            name=project_name,
            project_billing_info=project_billing_info,
        )
        if response.billing_enabled or response.billing_account_name:
            raise RuntimeError("Cloud Billing API did not confirm the empty billing assignment")


def _emit(line: str) -> None:
    print(line, flush=True)


@functions_framework.cloud_event
def stop_billing(cloud_event: object) -> None:
    """Handle a Cloud Billing budget notification delivered through Pub/Sub."""

    handle_budget_notification(
        getattr(cloud_event, "data", None),
        expected_billing_account_id=_required_environment("EXPECTED_BILLING_ACCOUNT_ID"),
        expected_budget_id=_required_environment("EXPECTED_BUDGET_ID"),
        gateway_factory=GoogleBillingGateway,
        emit=_emit,
    )
