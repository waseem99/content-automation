from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p7-readiness-report.md")
CHECKLIST = Path("docs/operations/p7-closeout-checklist.md")


def test_p7_readiness_report_records_scope_and_evidence() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "#106",
        "#107",
        "#108",
        "#109",
        "#110",
        "#111",
        "PR #112",
        "PR #113",
        "PR #114",
        "PR #115",
        "PR #116",
        "PR #117",
        "Prior green CI evidence",
    ]:
        assert term in content


def test_p7_readiness_report_records_runtime_surfaces() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "Dockerfile",
        ".dockerignore",
        "src.operator_api.entrypoint:app",
        "GET /health",
        "GET /runtime/config",
        "GET /runtime/ready",
        "GET /runtime/observability",
        "src/operator_api/observability.py",
        "docs/operations/p7-step-04.md",
        "docs/operations/p7-step-05.md",
    ]:
        assert term in content


def test_p7_readiness_report_records_validation_files() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "tests/integration/test_p7_step_*.py",
        "test_p7_step_01.py",
        "test_p7_step_02.py",
        "test_p7_step_03.py",
        "test_p7_step_04.py",
        "test_p7_step_05.py",
        "test_p7_step_06.py",
    ]:
        assert term in content


def test_p7_closeout_checklist_records_child_issues() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "#106 — Runtime container package completed",
        "#107 — Runtime health and readiness checks completed",
        "#108 — Observability instrumentation completed",
        "#109 — Static UI API wiring contract completed",
        "#110 — Operator runbook updates completed",
        "#111 — P7 readiness closeout prepared",
        "P7 readiness report is added",
        "P7 closeout checklist is added",
        "Final validation exists in `tests/integration/test_p7_step_06.py`",
    ]:
        assert term in content


def test_p7_closeout_docs_preserve_guardrails() -> None:
    combined = REPORT.read_text(encoding="utf-8") + CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
        "No public production launch.",
        "No private runtime values.",
    ]:
        assert term in combined
