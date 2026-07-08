from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p19-step-02.md")


def test_p19_access_review_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p19-step-01.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p18-step-05.md",
        "docs/operations/p17-step-04.md",
        "docs/operations/p17-step-02.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p14-step-06.md",
    ]:
        assert term in content


def test_p19_access_review_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This access review is documentation-only.",
        "grant production access",
        "remove production access",
        "modify repository permissions",
        "approve production launch",
        "schedule production launch",
        "execute release activities",
        "bypass workflow gates",
        "publish access material",
        "export access evidence",
        "replace manual approval",
    ]:
        assert term in content


def test_p19_access_review_documents_principles_boundaries_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "grant only the access needed for the assigned role",
        "separate operator, reviewer, support, release, incident, evidence, and admin responsibilities",
        "require owner approval for permission changes",
        "require periodic access review",
        "remove stale or ownerless access through a tracked route",
        "avoid shared accounts",
        "avoid undocumented exceptions",
        "avoid permanent elevated access",
        "record evidence-safe access summaries only",
        "admin access boundary",
        "reviewer access boundary",
        "operator access boundary",
        "support owner access boundary",
        "release owner access boundary",
        "incident owner access boundary",
        "evidence owner access boundary",
        "documentation owner access boundary",
        "backup owner access boundary",
        "allowed actions, prohibited actions, escalation triggers, and evidence expectations",
        "access item identifier",
        "role name",
        "access area",
        "current access summary",
        "requested access summary",
        "approval route",
        "evidence source",
        "least-privilege status",
        "exception status",
        "review cadence",
        "validation requirement",
        "closure criteria",
    ]:
        assert term in content


def test_p19_access_review_documents_routes_cadence_exceptions_evidence_and_escalation() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "no access change required",
        "approve with named owner",
        "approve with time limit",
        "reject with reason",
        "remove stale access",
        "request more evidence",
        "escalate to admin owner",
        "escalate to evidence owner",
        "escalate to security incident response",
        "create implementation issue",
        "block by guardrail",
        "Access changes cannot be automatic.",
        "per role change",
        "before release decision",
        "after incident",
        "after support escalation",
        "after owner change",
        "monthly during steady operation",
        "before phase closeout",
        "exception identifier",
        "exception owner",
        "business reason summary",
        "approval owner",
        "expiry or review point",
        "compensating control",
        "Permission exceptions cannot be permanent.",
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized access notes",
        "summarized approval notes",
        "summarized reviewer notes",
        "summarized exception notes",
        "evidence archive entry names",
        "raw permission dumps with restricted values",
        "access owner is missing",
        "requested access exceeds role boundary",
        "elevated access has no expiry",
        "stale access is detected",
        "shared account is detected",
        "permission exception lacks approval",
        "access request implies production launch",
    ]:
        assert term in content


def test_p19_access_review_documents_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "role name is missing",
        "access area is missing",
        "owner is missing",
        "reviewer is missing",
        "approval route is missing",
        "evidence source is missing",
        "evidence sensitivity is missing",
        "least-privilege status is missing",
        "review cadence is missing",
        "exception has no expiry or review point",
        "exception is permanent",
        "access change is automatic",
        "production launch is implied",
        "workflow gate bypass is requested",
        "evidence contains secret values",
        "evidence contains private runtime values",
        "customer data export is requested",
        "external export is requested",
        "No automatic approval.",
        "No automatic release.",
        "No automatic access changes.",
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
