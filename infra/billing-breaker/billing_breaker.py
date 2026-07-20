"""Pure decision engine for the project billing circuit breaker."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

PROJECT_ID = "n8-memory-palace"
PROJECT_RESOURCE = f"projects/{PROJECT_ID}"


class BillingGateway(Protocol):
    """The one destructive cloud operation used by the breaker."""

    def set_billing_account(self, *, project_name: str, billing_account_name: str) -> None:
        """Set the project's billing account to the requested resource name."""


class InvalidNotification(ValueError):
    """A notification that cannot safely authorize the detach operation."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class BudgetNotification:
    """Validated fields needed for the circuit-breaker decision."""

    message_id: str
    billing_account_id: str
    budget_id: str
    cost_amount: Decimal
    budget_amount: Decimal


DecisionEmitter = Callable[[str], None]
GatewayFactory = Callable[[], BillingGateway]


def _reject_json_constant(value: str) -> None:
    raise InvalidNotification(f"non_finite_json_number:{value}")


def _mapping(value: object, *, reason: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidNotification(reason)
    return value


def _amount(value: object, *, field: str, strictly_positive: bool) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise InvalidNotification(f"invalid_{field}")
    if value < 0 or (strictly_positive and value == 0):
        raise InvalidNotification(f"invalid_{field}")
    return value


def _message_id(event_data: object) -> str:
    if not isinstance(event_data, Mapping):
        return "unknown"
    message = event_data.get("message")
    if not isinstance(message, Mapping):
        return "unknown"
    value = message.get("messageId", message.get("message_id"))
    return value if isinstance(value, str) and value else "unknown"


def parse_budget_notification(
    event_data: object,
    *,
    expected_billing_account_id: str,
    expected_budget_id: str,
) -> BudgetNotification:
    """Validate a Pub/Sub CloudEvent data object and decode its budget payload."""

    envelope = _mapping(event_data, reason="event_data_not_object")
    message = _mapping(envelope.get("message"), reason="message_missing")
    attributes = _mapping(message.get("attributes"), reason="attributes_missing")

    if attributes.get("schemaVersion") != "1.0":
        raise InvalidNotification("schema_version_mismatch")
    if attributes.get("billingAccountId") != expected_billing_account_id:
        raise InvalidNotification("billing_account_mismatch")
    if attributes.get("budgetId") != expected_budget_id:
        raise InvalidNotification("budget_id_mismatch")

    encoded = message.get("data")
    if not isinstance(encoded, str):
        raise InvalidNotification("message_data_missing")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        decoded = raw.decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError, binascii.Error) as exc:
        raise InvalidNotification("message_data_not_base64_utf8") from exc

    try:
        payload = json.loads(
            decoded,
            parse_float=Decimal,
            parse_int=Decimal,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise InvalidNotification("message_data_not_json") from exc
    payload = _mapping(payload, reason="budget_payload_not_object")

    if payload.get("currencyCode") != "USD":
        raise InvalidNotification("currency_mismatch")
    if payload.get("budgetAmountType") != "SPECIFIED_AMOUNT":
        raise InvalidNotification("budget_amount_type_mismatch")

    return BudgetNotification(
        message_id=_message_id(envelope),
        billing_account_id=expected_billing_account_id,
        budget_id=expected_budget_id,
        cost_amount=_amount(
            payload.get("costAmount"), field="cost_amount", strictly_positive=False
        ),
        budget_amount=_amount(
            payload.get("budgetAmount"), field="budget_amount", strictly_positive=True
        ),
    )


def _emit(
    emit: DecisionEmitter,
    *,
    action: str,
    severity: str,
    expected_billing_account_id: str,
    expected_budget_id: str,
    message_id: str,
    cost_amount: Decimal | None = None,
    budget_amount: Decimal | None = None,
    reason: str | None = None,
    error_type: str | None = None,
) -> None:
    record: dict[str, str] = {
        "action": action,
        "billing_account_id": expected_billing_account_id,
        "budget_id": expected_budget_id,
        "component": "billing-breaker",
        "message_id": message_id,
        "project_id": PROJECT_ID,
        "severity": severity,
    }
    if cost_amount is not None:
        record["cost_amount"] = str(cost_amount)
    if budget_amount is not None:
        record["budget_amount"] = str(budget_amount)
    if reason is not None:
        record["reason"] = reason
    if error_type is not None:
        record["error_type"] = error_type
    emit(json.dumps(record, separators=(",", ":"), sort_keys=True))


def handle_budget_notification(
    event_data: object,
    *,
    expected_billing_account_id: str,
    expected_budget_id: str,
    gateway_factory: GatewayFactory,
    emit: DecisionEmitter,
) -> str:
    """Acknowledge one notification, detaching billing exactly at or over budget."""

    try:
        notification = parse_budget_notification(
            event_data,
            expected_billing_account_id=expected_billing_account_id,
            expected_budget_id=expected_budget_id,
        )
    except InvalidNotification as exc:
        _emit(
            emit,
            action="invalid_notification",
            severity="WARNING",
            expected_billing_account_id=expected_billing_account_id,
            expected_budget_id=expected_budget_id,
            message_id=_message_id(event_data),
            reason=exc.reason,
        )
        return "invalid_notification"

    common = {
        "expected_billing_account_id": expected_billing_account_id,
        "expected_budget_id": expected_budget_id,
        "message_id": notification.message_id,
        "cost_amount": notification.cost_amount,
        "budget_amount": notification.budget_amount,
    }
    if notification.cost_amount < notification.budget_amount:
        _emit(emit, action="below_budget", severity="INFO", **common)
        return "below_budget"

    _emit(emit, action="detach_requested", severity="CRITICAL", **common)
    try:
        gateway_factory().set_billing_account(
            project_name=PROJECT_RESOURCE,
            billing_account_name="",
        )
    except Exception as exc:
        _emit(
            emit,
            action="detach_failed",
            severity="ERROR",
            error_type=type(exc).__name__,
            **common,
        )
        raise

    _emit(emit, action="billing_detached", severity="CRITICAL", **common)
    return "billing_detached"
