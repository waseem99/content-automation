from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p11-step-03.md")


def test_p11_incident_review_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p11-step-01.md",
        "docs/operations/p11-step-02.md",
        "docs/operations/p10-step-05.md",
        "docs/operations/p10-step-04.md",
    ]:
        assert term in content


def test_p11_incident_review_documents_intake_and_severity() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "incident date",
        "alert or manual report source",
        "affected surface",
        "customer or operator impact",
        "rollback decision status",
        "S1: service unavailable, data safety concern, or protected route failure",
        "S2: degraded health, repeated failures, or rollback decision needed",
        "Severity may be lowered only after evidence review.",
    ]:
        assert term in content


def test_p11_incident_review_documents_cadence_agenda_and_actions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "S1 within one business day",
        "S2 within two business days",
        "Recurring review continues until all critical actions are closed.",
        "Review detection path and alert route.",
        "Review rollback or forward-fix decision.",
        "Assign corrective actions.",
        "backup owner",
        "validation method",
        "closure evidence",
    ]:
        assert term in content


def test_p11_incident_review_documents_closure_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "required evidence is recorded",
        "decision owner approves closure",
        "protected route failure is unresolved",
        "critical action has no owner",
        "decision owner has not approved closure",
        "No incident closure without evidence.",
        "No downgrade without evidence review.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No secret values in evidence.",
    ]:
        assert term in content
