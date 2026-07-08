from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p12-step-05.md")


def test_p12_exception_handling_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p12-step-01.md",
        "docs/operations/p12-step-02.md",
        "docs/operations/p12-step-03.md",
        "docs/operations/p12-step-04.md",
    ]:
        assert term in content


def test_p12_exception_handling_documents_request_fields_and_approvals() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "exception ID",
        "exception owner",
        "affected control or process",
        "risk statement",
        "compensating control",
        "requested expiry date",
        "exception owner accepts ownership",
        "affected control owner confirms impact",
        "decision owner approves or rejects",
        "evidence archive owner confirms archive location",
    ]:
        assert term in content


def test_p12_exception_handling_documents_time_limits_controls_and_review() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "every exception must have an expiry date",
        "critical exceptions require weekly review",
        "expired exceptions must be closed or re-approved",
        "permanent exceptions are not allowed",
        "mitigation description",
        "validation method",
        "failure action",
        "during KPI reporting",
        "during audit control review",
    ]:
        assert term in content


def test_p12_exception_handling_documents_closure_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "decision owner accepts closure",
        "KPI report is updated if applicable",
        "exception owner is missing",
        "affected control is unknown",
        "expiry date is missing",
        "exception hides a critical production failure",
        "No permanent exceptions.",
        "No exception without expiry date.",
        "No exception without compensating control.",
        "No exception without decision owner approval.",
        "No exception that hides critical production failure.",
        "No workflow gate bypass.",
    ]:
        assert term in content
