from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p9-step-04.md")


def test_p9_dashboard_review_references_prior_operations_docs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p8-step-05.md",
        "docs/operations/p9-step-01.md",
        "docs/operations/p9-step-03.md",
        "dashboard panel availability",
        "alert routing rehearsal",
        "guardrail review",
    ]:
        assert term in content


def test_p9_dashboard_review_documents_panels_metrics_and_labels() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "service health",
        "readiness and migration state",
        "API request volume and latency",
        "workflow and operator actions",
        "queue and audit visibility",
        "runtime_startup_total",
        "runtime_healthcheck_total",
        "runtime_readiness_total",
        "api_request_total",
        "api_request_duration_ms",
        "workflow_action_total",
        "operator_approval_action_total",
        "queue_item_count",
        "audit_report_request_total",
        "route_name",
        "status_family",
        "outcome",
        "action_name",
        "review_type",
    ]:
        assert term in content


def test_p9_dashboard_review_documents_alert_candidates_and_routing() -> None:
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
        "alert owner or group is identified",
        "route for rollback decision owner is known",
        "escalation path is recorded",
        "no secret values are included in alert payloads",
    ]:
        assert term in content


def test_p9_dashboard_review_documents_routes_evidence_and_stop_conditions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "GET /health",
        "GET /runtime/ready",
        "GET /runtime/config",
        "GET /runtime/observability",
        "GET /workflows/{workflow_run_id}/queue",
        "GET /workflows/{workflow_run_id}/dashboard/queue",
        "GET /workflows/{workflow_run_id}/audit",
        "dashboard review date",
        "routing owner or group for each alert family",
        "unresolved gaps and owner",
        "readiness signal is unavailable",
        "alert owner is unknown",
        "dashboards use unbounded labels",
    ]:
        assert term in content


def test_p9_dashboard_review_preserves_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "No secret values in dashboards.",
        "No private runtime values in dashboards.",
        "No raw operator key in telemetry.",
        "No full request body in telemetry.",
        "No unbounded label values.",
        "No public production launch.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
    ]:
        assert term in content
