from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p15-step-05.md")


def test_p15_documentation_freshness_references_previous_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p15-step-01.md",
        "docs/operations/p15-step-02.md",
        "docs/operations/p15-step-03.md",
        "docs/operations/p15-step-04.md",
        "docs/operations/p14-readiness-report.md",
        "docs/operations/p14-closeout-checklist.md",
    ]:
        assert term in content


def test_p15_documentation_freshness_documents_coverage_and_categories() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "production runbooks",
        "readiness reports",
        "closeout checklists",
        "evidence maps",
        "ownership records",
        "validation references",
        "release guardrail references",
        "access review records",
        "control testing records",
        "cost and performance review records",
        "support and incident trend records",
        "CI evidence references",
        "current",
        "stale owner",
        "stale reviewer",
        "stale validation reference",
        "stale evidence reference",
        "missing issue or PR link",
        "missing closure evidence",
        "missing guardrail reference",
        "outdated process step",
        "duplicate or conflicting guidance",
        "restricted value risk",
        "external export risk",
    ]:
        assert term in content


def test_p15_documentation_freshness_documents_fields_cadence_and_actions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "finding identifier",
        "document path",
        "freshness category",
        "source evidence",
        "required action",
        "action owner",
        "target review date",
        "validation requirement",
        "linked issue or PR when applicable",
        "evidence archive entry",
        "before P15 closeout",
        "after major operational phase closeout",
        "after material incident review",
        "after control testing updates",
        "after access certification updates",
        "after cost and performance review updates",
        "update document",
        "create implementation issue",
        "create backlog item",
        "update ownership record",
        "update evidence reference",
        "update validation reference",
        "remove duplicate guidance",
        "mark as current with evidence",
        "request more evidence",
        "reject with reason",
        "block by guardrail",
    ]:
        assert term in content


def test_p15_documentation_freshness_documents_evidence_and_ownership() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "document path references",
        "issue or PR numbers",
        "CI run identifiers",
        "readiness report references",
        "closeout checklist references",
        "evidence archive entry names",
        "summarized owner review notes",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "document owner",
        "validation owner when validation reference changes",
        "evidence owner when evidence reference changes",
        "escalation owner for restricted value risk or conflicting guidance",
        "Ownerless freshness findings cannot close as current or complete.",
    ]:
        assert term in content


def test_p15_documentation_freshness_documents_closure_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "required action or current decision",
        "linked issue or PR when implementation occurred",
        "validation result when validation reference changed",
        "no unresolved restricted value risk",
        "no external export request",
        "document path is missing",
        "source evidence is missing",
        "owner is missing",
        "reviewer is missing",
        "action owner is missing for required action",
        "validation requirement is missing when validation reference changes",
        "evidence archive entry is missing",
        "finding contains secret values",
        "finding contains private runtime values",
        "external export is requested",
        "workflow gate bypass is requested",
        "automatic approval is requested",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No customer data exports.",
        "No external package exports.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content
