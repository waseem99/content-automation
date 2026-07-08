from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p11-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p11_weekly_review_references_p10_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p10-readiness-report.md",
        "docs/operations/p10-closeout-checklist.md",
        "docs/operations/p10-step-04.md",
        "after P10 closeout",
    ]:
        assert term in content


def test_p11_weekly_review_documents_cadence_roles_and_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Run once per week during the stabilization period.",
        "decision owner",
        "operations owner",
        "monitoring owner",
        "alert routing owner",
        "incident review owner",
        "evidence archive owner",
        "rollback owner",
        "A named backup must be recorded for every required role.",
        "latest dashboard summary",
        "rollback readiness status",
    ]:
        assert term in content


def test_p11_weekly_review_documents_agenda_outputs_and_decisions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Confirm rollout status and exposure boundary.",
        "Review health and readiness signals.",
        "Review alert noise, missed signals, and routed incidents.",
        "Review evidence archive completeness.",
        "Assign action owners and due dates.",
        "review date",
        "new action items",
        "risks accepted",
        "continue current exposure",
        "request rollback decision review",
    ]:
        assert term in content


def test_p11_weekly_review_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "health or readiness signal is missing",
        "alert route is unavailable",
        "rollback owner is unavailable",
        "evidence archive contains secret values",
        "protected route anomaly appears",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No exposure expansion without weekly review decision.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
    ]:
        assert term in content


def test_p11_weekly_review_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p11_step_*.py" in harness
