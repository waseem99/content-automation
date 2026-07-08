from __future__ import annotations

from typing import Any

SERVICE_NAME = "content-automation-operator-api"

EVENT_FIELDS = (
    "timestamp",
    "level",
    "event_name",
    "service",
    "runtime_environment",
    "request_id",
    "workflow_id",
    "operator_id",
    "route_name",
    "status_code",
    "outcome",
    "duration_ms",
    "error_type",
    "error_summary",
)

METRIC_NAMES = (
    "runtime_startup_total",
    "runtime_healthcheck_total",
    "runtime_readiness_total",
    "api_request_total",
    "api_request_duration_ms",
    "workflow_action_total",
    "operator_approval_action_total",
    "audit_report_request_total",
    "queue_item_count",
)

LABEL_FIELDS = (
    "route_name",
    "status_family",
    "outcome",
    "action_name",
    "review_type",
)

GUARDRAILS = (
    "no_full_request_body",
    "no_private_runtime_values",
    "no_raw_operator_key",
    "no_unbounded_label_values",
    "no_external_collector_required",
)


def observability_contract() -> dict[str, Any]:
    return {
        "ok": True,
        "kind": "runtime_observability_contract",
        "service": SERVICE_NAME,
        "event_fields": list(EVENT_FIELDS),
        "metric_names": list(METRIC_NAMES),
        "label_fields": list(LABEL_FIELDS),
        "guardrails": list(GUARDRAILS),
    }


def runtime_event(
    *,
    event_name: str,
    outcome: str,
    request_id: str | None = None,
    workflow_id: str | None = None,
    operator_id: str | None = None,
    route_name: str | None = None,
    status_code: int | None = None,
    duration_ms: int | None = None,
    level: str = "INFO",
    error_type: str | None = None,
    error_summary: str | None = None,
) -> dict[str, Any]:
    return {
        "level": level.upper(),
        "event_name": event_name,
        "service": SERVICE_NAME,
        "request_id": request_id,
        "workflow_id": workflow_id,
        "operator_id": operator_id,
        "route_name": route_name,
        "status_code": status_code,
        "outcome": outcome,
        "duration_ms": duration_ms,
        "error_type": error_type,
        "error_summary": error_summary,
    }


def runtime_metric(name: str, value: int | float, labels: dict[str, str] | None = None) -> dict[str, Any]:
    safe_labels = labels or {}
    unsupported = set(safe_labels).difference(LABEL_FIELDS)
    if unsupported:
        raise ValueError(f"unsupported metric labels: {sorted(unsupported)}")
    if name not in METRIC_NAMES:
        raise ValueError(f"unsupported metric name: {name}")
    return {
        "name": name,
        "value": value,
        "labels": dict(safe_labels),
    }
