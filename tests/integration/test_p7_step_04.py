from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p7-step-04.md")
UI = Path("src/operator_ui/static/index.html")


def test_p7_ui_wiring_contract_documents_runtime_routes() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Runtime status wiring",
        "GET /health",
        "GET /runtime/config",
        "GET /runtime/ready",
        "GET /runtime/observability",
        "readiness checks",
        "observability contract",
    ]

    for term in required_terms:
        assert term in content


def test_p7_ui_wiring_contract_documents_operator_flow_routes() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Queue wiring",
        "GET /workflows/{workflow_run_id}/queue",
        "GET /workflows/{workflow_run_id}/dashboard/queue",
        "Demo run wiring",
        "GET /demo/scenario",
        "POST /demo/{workflow_run_id}/start",
        "POST /demo/{workflow_run_id}/approve-current",
        "GET /demo/{workflow_run_id}/status",
        "Audit report wiring",
        "GET /workflows/{workflow_run_id}/audit",
    ]

    for term in required_terms:
        assert term in content


def test_p7_ui_wiring_contract_documents_empty_and_error_states() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Empty state",
        "Error state",
        "show waiting state",
        "show no review items when count is zero",
        "show that no scenario has been loaded yet",
        "show no audit report loaded until a workflow id is supplied",
        "show route name, status code, and safe error summary",
        "HTTP 401",
        "operator access is required",
    ]

    for term in required_terms:
        assert term in content


def test_p7_ui_wiring_contract_matches_existing_static_screen_ids() -> None:
    html = UI.read_text(encoding="utf-8")

    required_terms = [
        'data-screen="runtime-status"',
        'data-screen="queue"',
        'data-screen="demo-run"',
        'data-screen="audit-report"',
        'data-screen="guardrails"',
        'data-component="queue-card"',
        'data-component="demo-actions"',
        'data-component="audit-sections"',
    ]

    for term in required_terms:
        assert term in html


def test_p7_ui_wiring_contract_preserves_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "No frontend framework is added.",
        "No build step is added.",
        "No hidden business logic is added.",
        "No publishing action is present.",
        "No scheduling action is present.",
        "No rendering action is present.",
        "No external export action is present.",
        "No workflow gate is bypassed.",
        "No private runtime values are displayed.",
    ]

    for term in required_terms:
        assert term in content
