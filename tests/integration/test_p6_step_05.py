from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p6-step-05.md")


def test_p6_pilot_runbook_documents_startup_and_status_checks() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Start runtime",
        "uvicorn src.operator_api.entrypoint:app --host 127.0.0.1 --port 8000",
        "Check health",
        "GET /health",
        "Check runtime status",
        "GET /runtime/config",
        "database configured flag",
        "access required flag",
        "no sensitive values are returned",
    ]

    for term in required_terms:
        assert term in content


def test_p6_pilot_runbook_documents_demo_and_gate_flow() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Prepare workflow id",
        "Run demo scenario",
        "GET /demo/scenario",
        "POST /demo/{workflow_run_id}/start",
        "approve_packet",
        "Approve packet gate",
        "Approve output gate",
        "approve_output",
        "Confirm final stop point",
        "continue_p3_delivery",
    ]

    for term in required_terms:
        assert term in content


def test_p6_pilot_runbook_documents_audit_and_result_capture() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Inspect audit report",
        "GET /workflows/{workflow_run_id}/audit",
        "workflow summary",
        "status summary",
        "event timeline",
        "reviews are present",
        "Record pilot result",
        "completed gates",
        "final stop point",
        "follow-on issue",
    ]

    for term in required_terms:
        assert term in content


def test_p6_pilot_runbook_documents_pass_fail_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Pass criteria",
        "Fail criteria",
        "health route succeeds",
        "runtime config route succeeds",
        "packet gate is approved explicitly",
        "output gate is approved explicitly",
        "workflow skips a review gate",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No public production launch.",
    ]

    for term in required_terms:
        assert term in content
