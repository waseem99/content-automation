from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p9-step-05.md")


def test_p9_go_no_go_checklist_references_rehearsal_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p9-step-01.md",
        "docs/operations/p9-step-02.md",
        "docs/operations/p9-step-03.md",
        "docs/operations/p9-step-04.md",
        "deployment dry-run result",
        "restore rehearsal result",
        "rollback rehearsal result",
        "dashboard review result",
        "alert routing review result",
    ]:
        assert term in content


def test_p9_go_no_go_checklist_documents_decision_options_and_evidence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "go;",
        "no-go;",
        "go with documented limitations",
        "defer pending evidence",
        "repeat rehearsal",
        "latest exact-head CI result",
        "backup availability confirmation",
        "rollback owner confirmation",
        "decision owner confirmation",
        "unresolved gap list",
    ]:
        assert term in content


def test_p9_go_no_go_checklist_documents_approval_and_criteria() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "deployment operator sign-off",
        "database operator sign-off",
        "dashboard or alert reviewer sign-off",
        "security or guardrail reviewer sign-off",
        "decision owner sign-off",
        "Approval must be human-recorded and must not be automatic.",
        "deployment dry-run passed",
        "restore rehearsal passed",
        "rollback rehearsal passed",
        "latest CI green",
        "protected routes verified",
        "no workflow gate bypass needed",
    ]:
        assert term in content


def test_p9_go_no_go_checklist_documents_no_go_limitations_and_stop_conditions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "deployment dry-run failed",
        "restore rehearsal failed",
        "rollback rehearsal failed",
        "health or readiness checks failed",
        "protected route access is not enforced",
        "latest CI is not green",
        "Go with documented limitations",
        "limitation is non-critical",
        "owner and due date are recorded",
        "Stop condition review",
        "rollback path is unknown",
        "alert route is unknown",
    ]:
        assert term in content


def test_p9_go_no_go_checklist_preserves_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "No automatic approval.",
        "No workflow gate bypass.",
        "No public production launch without explicit go decision.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content
