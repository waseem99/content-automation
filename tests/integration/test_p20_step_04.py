from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p20-step-04.md")


def test_p20_retention_deletion_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p20-step-01.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p19-step-03.md",
        "docs/operations/p19-readiness-report.md",
        "docs/operations/p16-step-05.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p18-step-05.md",
    ]:
        assert term in content


def test_p20_retention_deletion_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This data retention and deletion evidence pack is documentation-only.",
        "collect production data",
        "delete production records",
        "change retention settings",
        "export customer data",
        "expose restricted values",
        "approve production launch",
        "schedule production launch",
        "publish retention evidence",
        "render retention evidence",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p20_retention_deletion_documents_categories_decisions_routes_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "retention decisions",
        "deletion route decisions",
        "replacement route decisions",
        "redaction decisions",
        "rejected evidence decisions",
        "evidence owner review",
        "reviewer confirmation",
        "sensitivity classification",
        "privacy escalation",
        "compliance closeout linkage",
        "retain summary only",
        "retain issue or PR reference only",
        "retain CI run identifier only",
        "retain merge commit reference only",
        "retain evidence archive entry name only",
        "redact and retain summary",
        "delete or replace evidence",
        "reject evidence",
        "escalate to evidence owner",
        "escalate to security incident response",
        "block by guardrail",
        "Retention decisions must not retain customer data exports",
        "remove restricted evidence from notes",
        "replace with issue or PR reference",
        "replace with CI run identifier",
        "replace with merge commit reference",
        "replace with summarized non-sensitive note",
        "replace with evidence archive entry name",
        "route to privacy owner",
        "create follow-up issue",
        "Deletion route documentation must not include the restricted value being removed.",
        "evidence item identifier",
        "data category",
        "source location",
        "sensitivity class",
        "retention decision",
        "deletion route",
        "replacement route",
        "redaction status",
        "evidence source",
        "action route",
        "review cadence",
        "validation requirement",
        "closure criteria",
    ]:
        assert term in content


def test_p20_retention_deletion_documents_sensitivity_owner_review_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "public reference",
        "internal summary",
        "restricted summary",
        "restricted value suspected",
        "restricted value confirmed",
        "customer data suspected",
        "customer data confirmed",
        "blocked by guardrail",
        "require escalation and cannot close without owner review",
        "evidence class is allowed",
        "sensitivity class is recorded",
        "retention decision is valid",
        "deletion route is recorded when required",
        "replacement route is recorded when required",
        "redaction status is complete when required",
        "evidence source is summary-only",
        "closure criteria are met",
        "no restricted values remain",
        "per PR closeout",
        "before compliance closeout",
        "after privacy escalation",
        "after security incident",
        "after support pattern",
        "after retention rule change",
        "monthly during steady operation",
    ]:
        assert term in content


def test_p20_retention_deletion_documents_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "evidence item identifier is missing",
        "data category is missing",
        "source location is missing",
        "owner is missing",
        "reviewer is missing",
        "sensitivity class is missing",
        "retention decision is missing",
        "deletion route is missing when deletion is required",
        "replacement route is missing when replacement is required",
        "redaction status is missing when redaction is required",
        "evidence source is missing",
        "action owner is missing for required action",
        "restricted value remains in evidence",
        "customer data export is requested",
        "private runtime value is present",
        "secret value is present",
        "raw credential is present",
        "production token is present",
        "external export is requested",
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
