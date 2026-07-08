from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p19-step-05.md")


def test_p19_security_incident_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p19-step-01.md",
        "docs/operations/p19-step-02.md",
        "docs/operations/p19-step-03.md",
        "docs/operations/p19-step-04.md",
        "docs/operations/p18-step-04.md",
        "docs/operations/p17-step-05.md",
        "docs/operations/p16-step-03.md",
    ]:
        assert term in content


def test_p19_security_incident_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This playbook is documentation-only.",
        "create a live incident system",
        "grant security access",
        "execute containment actions",
        "rotate secrets",
        "delete production data",
        "export incident evidence",
        "approve production launch",
        "schedule production launch",
        "bypass workflow gates",
        "replace named incident ownership",
    ]:
        assert term in content


def test_p19_security_incident_documents_categories_severity_triage_and_escalation() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "suspected secret exposure",
        "confirmed secret exposure",
        "unauthorized access concern",
        "permission misuse concern",
        "dependency vulnerability concern",
        "supply-chain integrity concern",
        "customer data exposure concern",
        "private runtime value exposure",
        "suspicious workflow activity",
        "restricted value found in logs",
        "informational",
        "low",
        "medium",
        "high",
        "critical",
        "exposure confidence",
        "customer impact",
        "secret sensitivity",
        "record incident identifier",
        "classify incident category",
        "assign incident owner",
        "identify evidence owner",
        "classify evidence sensitivity",
        "choose containment route",
        "choose escalation route",
        "create follow-up issue when implementation is required",
        "severity is high",
        "severity is critical",
        "secret exposure is confirmed",
        "customer data exposure is suspected",
        "unauthorized access is suspected",
        "dependency vulnerability is high or critical",
        "containment owner is missing",
    ]:
        assert term in content


def test_p19_security_incident_documents_containment_evidence_fields_and_closure() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "no containment required",
        "redact and replace evidence",
        "remove or replace restricted notes",
        "route to secret rotation owner",
        "route to access review owner",
        "route to dependency review owner",
        "route to support owner",
        "create implementation issue",
        "create security follow-up issue",
        "Containment route documentation must not include live secret values or private runtime values.",
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized incident notes",
        "summarized triage notes",
        "summarized containment notes",
        "summarized escalation notes",
        "summarized reviewer notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "private environment dumps",
        "customer data exports",
        "external package exports",
        "raw logs with restricted values",
        "raw incident dumps",
        "screenshots containing restricted values",
        "incident identifier",
        "incident category",
        "affected scope",
        "evidence owner",
        "containment route",
        "post-incident follow-up route",
        "restricted evidence is removed, redacted, or replaced",
        "follow-up issue exists when implementation is required",
    ]:
        assert term in content


def test_p19_security_incident_documents_followup_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "update secrets and configuration hardening",
        "update access control review",
        "update data handling review",
        "update dependency review",
        "update support playbook",
        "create documentation issue",
        "schedule owner review placeholder",
        "block by guardrail",
        "reject with reason",
        "incident owner is missing",
        "reviewer is missing",
        "evidence owner is missing",
        "severity is missing",
        "evidence source is missing",
        "evidence sensitivity is missing",
        "containment route is missing",
        "required escalation route is missing",
        "action owner is missing for required action",
        "restricted evidence remains unredacted",
        "confirmed secret exposure has no follow-up route",
        "suspected customer data exposure has no escalation route",
        "private runtime value is present",
        "customer data export is requested",
        "external package export is requested",
        "production launch is implied",
        "workflow gate bypass is requested",
        "No automatic approval.",
        "No automatic release.",
        "No automatic incident closure.",
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
