from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p8-step-05.md")


def test_p8_dashboard_notes_reference_observability_contract() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "GET /runtime/observability",
        "src/operator_api/observability.py",
        "P7 event fields",
        "metric names",
        "bounded labels",
        "telemetry guardrails",
    ]:
        assert term in content


def test_p8_dashboard_notes_document_required_panels_and_metrics() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Service health",
        "Readiness and migration state",
        "API request volume and latency",
        "Workflow and operator actions",
        "Queue and audit visibility",
        "runtime_startup_total",
        "runtime_healthcheck_total",
        "runtime_readiness_total",
        "api_request_total",
        "api_request_duration_ms",
        "workflow_action_total",
        "operator_approval_action_total",
        "queue_item_count",
        "audit_report_request_total",
    ]:
        assert term in content


def test_p8_dashboard_notes_document_bounded_labels_and_route_context() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "route_name",
        "status_family",
        "outcome",
        "action_name",
        "review_type",
        "GET /health",
        "GET /runtime/ready",
        "GET /workflows/{workflow_run_id}/queue",
        "GET /workflows/{workflow_run_id}/dashboard/queue",
        "GET /workflows/{workflow_run_id}/audit",
    ]:
        assert term in content


def test_p8_dashboard_notes_document_alerts_and_response_guidance() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "healthcheck failure",
        "readiness failure",
        "repeated 5xx responses",
        "database connection failure",
        "migration readiness failure",
        "protected route access anomaly",
        "queue growth above expected threshold",
        "workflow failure spike",
        "operator approval failure spike",
        "audit report request failure",
        "missing observability contract response",
        "identify affected environment",
        "confirm whether readiness is still true",
        "docs/operations/p8-step-03.md",
        "docs/operations/p8-step-04.md",
    ]:
        assert term in content


def test_p8_dashboard_notes_preserve_boundaries_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "dashboard vendor",
        "metrics collector",
        "log aggregation vendor",
        "incident management vendor",
        "No secret values in dashboards.",
        "No private runtime values in dashboards.",
        "No raw operator key in telemetry.",
        "No full request body in telemetry.",
        "No unbounded label values.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
        "No public production launch.",
    ]:
        assert term in content
