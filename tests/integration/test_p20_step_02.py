from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p20-step-02.md")


def test_p20_security_control_evidence_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p20-step-01.md",
        "docs/operations/p19-step-01.md",
        "docs/operations/p19-step-02.md",
        "docs/operations/p19-step-04.md",
        "docs/operations/p19-step-05.md",
        "docs/operations/p19-readiness-report.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p18-step-05.md",
    ]:
        assert term in content


def test_p20_security_control_evidence_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This security control evidence index is documentation-only.",
        "grant security access",
        "rotate secrets",
        "change configuration",
        "update dependencies",
        "execute incident containment",
        "approve production launch",
        "schedule production launch",
        "publish control evidence",
        "render control evidence",
        "export restricted evidence",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p20_security_control_evidence_documents_categories_mapping_classes_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "secrets and configuration hardening",
        "access control and permission review",
        "data handling and privacy controls",
        "dependency and supply-chain review",
        "security incident response",
        "evidence handling and retention",
        "release gate and exact-head CI controls",
        "manual approval controls",
        "owner and reviewer controls",
        "exception and stop-condition controls",
        "source runbook",
        "source issue or PR",
        "source merge commit when applicable",
        "source CI run identifier when applicable",
        "control owner",
        "reviewer",
        "evidence class",
        "evidence sensitivity",
        "review cadence",
        "closure criteria",
        "issue or PR reference",
        "CI run identifier",
        "merge commit reference",
        "summarized security review note",
        "summarized control owner note",
        "summarized reviewer note",
        "summarized access review note",
        "summarized incident review note",
        "summarized dependency review note",
        "evidence archive entry name",
        "secret value",
        "private runtime value",
        "raw credential",
        "production token",
        "customer data export",
        "external package export",
        "raw dependency archive",
        "raw incident dump",
        "raw log with restricted value",
        "screenshot containing restricted value",
        "security evidence identifier",
        "security control category",
        "control objective",
        "source document",
        "control status",
        "exception status",
        "validation requirement",
    ]:
        assert term in content


def test_p20_security_control_evidence_documents_statuses_exceptions_cadence_and_escalation() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "not started",
        "indexed",
        "reviewed",
        "reviewed with notes",
        "needs owner",
        "needs reviewer",
        "needs evidence",
        "needs escalation",
        "blocked by guardrail",
        "rejected with reason",
        "exception identifier",
        "exception owner",
        "business reason summary",
        "approver",
        "expiry or review point",
        "compensating control",
        "Exceptions cannot be permanent and cannot approve restricted evidence retention.",
        "per PR closeout",
        "before compliance closeout",
        "after security incident",
        "after access change",
        "after dependency change",
        "after configuration change",
        "after guardrail change",
        "monthly during steady operation",
        "control owner is missing",
        "evidence sensitivity is unclear",
        "exception lacks expiry",
        "high or critical issue is referenced",
        "secret exposure is suspected",
        "unauthorized access is suspected",
        "dependency vulnerability is high or critical",
        "workflow gate bypass is requested",
        "production launch is implied",
    ]:
        assert term in content


def test_p20_security_control_evidence_documents_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "security evidence identifier is missing",
        "security control category is missing",
        "control objective is missing",
        "source document is missing",
        "source issue or PR is missing",
        "control owner is missing",
        "reviewer is missing",
        "evidence class is missing",
        "evidence sensitivity is missing",
        "review cadence is missing",
        "exception is permanent",
        "exception lacks expiry or review point",
        "secret value is present",
        "private runtime value is present",
        "raw credential is present",
        "production token is present",
        "customer data export is requested",
        "external package export is requested",
        "production launch is implied",
        "workflow gate bypass is requested",
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No public production launch without explicit decision.",
        "No release without calendar entry.",
        "No release during blackout window.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No permanent exceptions.",
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
