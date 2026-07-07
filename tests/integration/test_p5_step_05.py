from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC_PATH = Path("docs/operations/p5-step-05.md")


def test_p5_ui_contract_documents_required_screens() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    required_screens = [
        "Queue screen",
        "Review detail screen",
        "Approval action flow",
        "Demo run screen",
        "Workflow audit screen",
        "Runtime status screen",
    ]

    for screen in required_screens:
        assert screen in content


def test_p5_ui_contract_maps_required_routes() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    required_routes = [
        "GET /health",
        "GET /runtime/config",
        "GET /workflows/{workflow_run_id}/queue",
        "GET /workflows/{workflow_run_id}/dashboard/queue",
        "GET /workflows/{workflow_run_id}/dashboard/schema",
        "POST /workflows/{workflow_run_id}/approvals",
        "GET /workflows/{workflow_run_id}/audit",
        "GET /demo/scenario",
        "POST /demo/{workflow_run_id}/start",
        "POST /demo/{workflow_run_id}/approve-current",
        "GET /demo/{workflow_run_id}/status",
    ]

    for route in required_routes:
        assert route in content


def test_p5_ui_contract_preserves_payload_expectations_and_guardrails() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    required_terms = [
        "workflow id",
        "operator id",
        "resource id",
        "optional rationale",
        "expected stop points",
        "event timeline",
        "stage executions",
        "packages",
        "manifests",
        "No frontend framework is added.",
        "No new API route is added.",
        "No publishing is added.",
        "No scheduling is added.",
        "No rendering is added.",
        "No external export is added.",
    ]

    for term in required_terms:
        assert term in content
