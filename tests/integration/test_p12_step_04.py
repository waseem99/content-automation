from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p12-step-04.md")


def test_p12_audit_controls_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p12-step-02.md",
        "docs/operations/p12-step-03.md",
        "docs/operations/p11-step-04.md",
        "docs/operations/p11-step-05.md",
    ]:
        assert term in content


def test_p12_audit_controls_documents_inventory_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "release approval",
        "rollback readiness",
        "access review",
        "alert routing",
        "incident review",
        "evidence archive indexing",
        "secret redaction",
        "exception expiry",
        "control ID",
        "control objective",
        "evidence source",
        "next review date",
    ]:
        assert term in content


def test_p12_audit_controls_documents_mapping_cadence_and_signoff() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "linked issue or PR",
        "source runbook",
        "evidence archive entry",
        "related KPI if applicable",
        "quarterly with access review",
        "monthly with KPI reporting for critical controls",
        "before external audit packaging",
        "control owner confirmation",
        "decision owner acceptance for critical controls",
    ]:
        assert term in content


def test_p12_audit_controls_documents_exceptions_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "exception owner",
        "compensating control",
        "expiry date",
        "control owner is missing",
        "critical control has no decision owner acceptance",
        "compensating control is missing",
        "No control closure without evidence.",
        "No critical control signoff without decision owner acceptance.",
        "No exception without expiry date.",
        "No missing compensating control for exception.",
        "No automatic approval.",
        "No workflow gate bypass.",
    ]:
        assert term in content
