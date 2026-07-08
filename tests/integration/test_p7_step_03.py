from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.operator_api.auth import OperatorAuthSettings
from src.operator_api.observability import observability_contract, runtime_event, runtime_metric
from src.operator_api.runtime_config import OperatorRuntimeSettings
from src.operator_api.runtime_factory import create_configured_app


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p7-step-03.md")


def test_observability_contract_contains_safe_event_and_metric_shapes() -> None:
    contract = observability_contract()

    assert contract["ok"] is True
    assert contract["kind"] == "runtime_observability_contract"
    assert contract["service"] == "content-automation-operator-api"

    for field in [
        "event_name",
        "service",
        "request_id",
        "workflow_id",
        "operator_id",
        "route_name",
        "status_code",
        "outcome",
        "duration_ms",
        "error_summary",
    ]:
        assert field in contract["event_fields"]

    for metric in [
        "runtime_startup_total",
        "runtime_healthcheck_total",
        "runtime_readiness_total",
        "api_request_total",
        "api_request_duration_ms",
        "workflow_action_total",
        "operator_approval_action_total",
        "audit_report_request_total",
        "queue_item_count",
    ]:
        assert metric in contract["metric_names"]


def test_observability_contract_route_is_available_on_runtime_app() -> None:
    settings = OperatorRuntimeSettings(_env_file=None)
    client = TestClient(create_configured_app(runtime_settings=settings, auth_settings=OperatorAuthSettings.disabled_for_local_tests()))

    response = client.get("/runtime/observability")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["kind"] == "runtime_observability_contract"
    assert "no_private_runtime_values" in payload["guardrails"]
    assert "no_external_collector_required" in payload["guardrails"]


def test_runtime_event_helper_returns_safe_shape_without_payload_body() -> None:
    event = runtime_event(
        event_name="runtime.ready",
        outcome="success",
        request_id="req-123",
        workflow_id="wf-123",
        operator_id="operator-1",
        route_name="/runtime/ready",
        status_code=200,
        duration_ms=15,
    )

    assert event["level"] == "INFO"
    assert event["event_name"] == "runtime.ready"
    assert event["service"] == "content-automation-operator-api"
    assert event["request_id"] == "req-123"
    assert event["workflow_id"] == "wf-123"
    assert event["operator_id"] == "operator-1"
    assert event["route_name"] == "/runtime/ready"
    assert event["status_code"] == 200
    assert event["duration_ms"] == 15
    assert "body" not in event
    assert "operator_key" not in event


def test_runtime_metric_helper_enforces_supported_names_and_labels() -> None:
    metric = runtime_metric(
        "runtime_readiness_total",
        1,
        labels={"route_name": "/runtime/ready", "outcome": "success"},
    )

    assert metric == {
        "name": "runtime_readiness_total",
        "value": 1,
        "labels": {"route_name": "/runtime/ready", "outcome": "success"},
    }

    with pytest.raises(ValueError, match="unsupported metric labels"):
        runtime_metric("runtime_readiness_total", 1, labels={"workflow_id": "wf-123"})

    with pytest.raises(ValueError, match="unsupported metric name"):
        runtime_metric("custom_unbounded_metric", 1)


def test_p7_observability_notes_cover_shape_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "GET /runtime/observability",
        "runtime_observability_contract",
        "Event shape",
        "Metric shape",
        "Label policy",
        "runtime_startup_total",
        "runtime_healthcheck_total",
        "runtime_readiness_total",
        "api_request_total",
        "operator_approval_action_total",
        "No external collector is added.",
        "No metrics service is added.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No full request body.",
        "No private runtime values.",
        "No raw operator key.",
        "No unbounded label values.",
    ]

    for term in required_terms:
        assert term in content
