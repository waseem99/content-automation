from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p7-step-05.md")


def test_p7_operator_runbook_documents_package_steps() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Build runtime package",
        "docker build -t content-automation-operator:local .",
        "Start runtime package",
        "docker run --rm -p 8000:8000 --env-file .env content-automation-operator:local",
        "Dockerfile",
        "requirements.txt",
        "src.operator_api.entrypoint:app",
    ]

    for term in required_terms:
        assert term in content


def test_p7_operator_runbook_documents_runtime_checks() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "GET /health",
        "GET /runtime/config",
        "GET /runtime/ready",
        "GET /runtime/observability",
        "database configured",
        "database reachable",
        "schema required",
        "schema ready",
        "migrations ready",
        "event fields are present",
        "metric names are present",
        "label fields are bounded",
    ]

    for term in required_terms:
        assert term in content


def test_p7_operator_runbook_links_ui_and_pilot_references() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "docs/operations/p7-step-04.md",
        "runtime status",
        "queue",
        "demo run",
        "audit report",
        "docs/operations/p6-step-05.md",
        "approve packet gate explicitly",
        "approve output gate explicitly",
        "continue_p3_delivery",
    ]

    for term in required_terms:
        assert term in content


def test_p7_operator_runbook_documents_pass_fail_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    required_terms = [
        "Pass criteria",
        "Fail criteria",
        "package builds",
        "runtime starts",
        "readiness succeeds",
        "observability contract is available",
        "pilot flow skips a review gate",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
        "No public production launch.",
        "No private runtime values.",
    ]

    for term in required_terms:
        assert term in content
