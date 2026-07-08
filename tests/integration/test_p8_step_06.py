from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p8-readiness-report.md")
CHECKLIST = Path("docs/operations/p8-closeout-checklist.md")


def test_p8_readiness_report_records_scope_and_evidence() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "#119",
        "#120",
        "#121",
        "#122",
        "#123",
        "#124",
        "PR #125",
        "PR #126",
        "PR #127",
        "PR #128",
        "PR #129",
        "This closeout PR",
        "Prior green CI evidence",
    ]:
        assert term in content


def test_p8_readiness_report_records_runtime_preparation_surfaces() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p8-step-01.md",
        "docs/operations/p8-step-02.md",
        ".env.production.example",
        "docs/operations/p8-step-03.md",
        "docs/operations/p8-step-04.md",
        "docs/operations/p8-step-05.md",
        "content-automation-operator-api",
        "GET /health",
        "GET /runtime/ready",
        "service health",
        "readiness and migration state",
    ]:
        assert term in content


def test_p8_readiness_report_records_validation_files() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "tests/integration/test_p8_step_*.py",
        "test_p8_step_01.py",
        "test_p8_step_02.py",
        "test_p8_step_03.py",
        "test_p8_step_04.py",
        "test_p8_step_05.py",
        "test_p8_step_06.py",
    ]:
        assert term in content


def test_p8_closeout_checklist_records_child_issues() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "#119 — Service definition completed",
        "#120 — Environment configuration completed",
        "#121 — Database backup and restore completed",
        "#122 — Rollback runbook completed",
        "#123 — Operational dashboards completed",
        "#124 — P8 production readiness closeout prepared",
        "P8 readiness report is added",
        "P8 closeout checklist is added",
        "Final validation exists in `tests/integration/test_p8_step_06.py`",
    ]:
        assert term in content


def test_p8_closeout_docs_preserve_guardrails_and_follow_on() -> None:
    combined = REPORT.read_text(encoding="utf-8") + CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "No secret values in git.",
        "No private runtime values in dashboards or public snapshots.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
        "No public production launch.",
        "Controlled deployment dry-run",
        "Restore rehearsal",
        "Rollback rehearsal",
        "Final go/no-go checklist",
    ]:
        assert term in combined
