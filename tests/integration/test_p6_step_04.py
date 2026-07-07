from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


HTML = Path("src/operator_ui/static/index.html")
CSS = Path("src/operator_ui/static/styles.css")
DOC = Path("docs/operations/p6-step-04.md")


def test_operator_ui_shell_includes_required_screens() -> None:
    content = HTML.read_text(encoding="utf-8")

    required_terms = [
        "runtime-status",
        "queue",
        "demo-run",
        "audit-report",
        "guardrails",
        "./styles.css",
    ]

    for term in required_terms:
        assert term in content


def test_operator_ui_shell_maps_existing_routes() -> None:
    content = HTML.read_text(encoding="utf-8")

    required_terms = [
        "GET /health",
        "GET /runtime/config",
        "GET /workflows/{workflow_run_id}/queue",
        "GET /workflows/{workflow_run_id}/dashboard/queue",
        "GET /demo/scenario",
        "POST /demo/{workflow_run_id}/start",
        "POST /demo/{workflow_run_id}/approve-current",
        "GET /demo/{workflow_run_id}/status",
        "GET /workflows/{workflow_run_id}/audit",
    ]

    for term in required_terms:
        assert term in content


def test_operator_ui_shell_includes_fields_and_sections() -> None:
    content = HTML.read_text(encoding="utf-8")

    required_terms = [
        "workflow_run_id",
        "operator",
        "resource_id",
        "expected_stop_points",
        "next_action",
        "queue-card",
        "demo-actions",
        "audit-sections",
        "Workflow summary",
        "Event timeline",
        "Stage executions",
        "Packages",
        "Manifests",
    ]

    for term in required_terms:
        assert term in content


def test_operator_ui_docs_preserve_scope_limits() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "No frontend framework is added.",
        "No build step is added.",
        "No API route is added.",
        "No publishing action is present.",
        "No scheduling action is present.",
        "No rendering action is present.",
        "No external export action is present.",
        "No workflow gate is bypassed.",
    ]

    for term in required_terms:
        assert term in content


def test_operator_ui_stylesheet_defines_layout_classes() -> None:
    content = CSS.read_text(encoding="utf-8")

    required_terms = [".shell", ".hero", ".panel", ".fields", ".card", ".actions", ".grid"]

    for term in required_terms:
        assert term in content
