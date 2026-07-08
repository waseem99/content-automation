from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p10-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p10_decision_record_references_p9_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p9-readiness-report.md",
        "docs/operations/p9-step-05.md",
        "docs/operations/p9-closeout-checklist.md",
        "P9 readiness report exists",
        "P9 go/no-go checklist exists",
        "deployment dry-run evidence exists",
        "restore rehearsal evidence exists",
        "rollback rehearsal evidence exists",
    ]:
        assert term in content


def test_p10_decision_record_documents_states_fields_and_evidence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "go;",
        "no-go;",
        "go with documented limitations",
        "defer pending evidence",
        "repeat rehearsal",
        "decision owner",
        "exact commit SHA",
        "exact PR number",
        "CI run IDs",
        "rehearsal evidence references",
        "stop condition review result",
        "latest exact-head CI is green",
    ]:
        assert term in content


def test_p10_decision_record_documents_human_approvals_and_limitations() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "decision owner approval",
        "deployment operator approval",
        "database operator approval",
        "dashboard or alert reviewer approval",
        "security or guardrail reviewer approval",
        "Approvals must be human-recorded and must not be automatic.",
        "limitation is non-critical",
        "limitation owner is recorded",
        "limitation due date is recorded",
    ]:
        assert term in content


def test_p10_decision_record_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "latest exact-head CI is not green",
        "rollback owner is unavailable",
        "backup availability is unknown",
        "protected route access is not enforced",
        "workflow gate bypass is required",
        "evidence includes secret values",
        "production exposure has no explicit go decision",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No production exposure without explicit go decision.",
        "No secret values in evidence.",
    ]:
        assert term in content


def test_p10_decision_record_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p10_step_*.py" in harness
