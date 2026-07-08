from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p20-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p20_privacy_evidence_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p19-step-03.md",
        "docs/operations/p19-readiness-report.md",
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-04.md",
        "docs/operations/p18-step-05.md",
        "docs/operations/p17-step-05.md",
        "docs/operations/p16-step-05.md",
        "docs/operations/p16-readiness-report.md",
    ]:
        assert term in content


def test_p20_privacy_evidence_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This privacy compliance evidence index is documentation-only.",
        "collect production data",
        "export customer data",
        "expose private runtime values",
        "store secret values",
        "change retention settings",
        "delete production records",
        "approve production launch",
        "schedule production launch",
        "publish compliance material",
        "render compliance material",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p20_privacy_evidence_documents_categories_classes_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "data handling controls",
        "evidence retention controls",
        "support note handling",
        "incident note handling",
        "customer data export restrictions",
        "private runtime value exclusions",
        "redaction and replacement decisions",
        "deletion route decisions",
        "owner and reviewer sign-off",
        "privacy stop conditions",
        "issue or PR reference",
        "CI run identifier",
        "merge commit reference",
        "summarized privacy review note",
        "summarized retention decision",
        "summarized deletion route note",
        "summarized redaction note",
        "summarized owner review note",
        "summarized support privacy note",
        "summarized incident privacy note",
        "evidence archive entry name",
        "customer data export",
        "private runtime value",
        "secret value",
        "raw credential",
        "production token",
        "raw support transcript with private data",
        "raw incident dump with private data",
        "screenshot containing restricted value",
        "evidence item identifier",
        "privacy control area",
        "source document",
        "source issue or PR",
        "evidence class",
        "evidence sensitivity",
        "retention decision",
        "deletion route when applicable",
        "redaction status",
        "review cadence",
        "escalation route",
        "validation requirement",
        "closure criteria",
    ]:
        assert term in content


def test_p20_privacy_evidence_documents_control_mapping_sensitivity_retention_and_escalation() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "allowed data handling",
        "prohibited data handling",
        "data category review",
        "evidence sensitivity classes",
        "log handling rules",
        "support and incident note rules",
        "export rules",
        "deletion or replacement routes",
        "public reference",
        "internal summary",
        "restricted summary",
        "restricted value suspected",
        "restricted value confirmed",
        "customer data suspected",
        "customer data confirmed",
        "blocked by guardrail",
        "require escalation",
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
        "Retention linkage must not authorize customer data export.",
        "per PR closeout",
        "before compliance closeout",
        "after support pattern",
        "after incident signal",
        "after retention rule change",
        "after privacy stop condition",
        "monthly during steady operation",
        "evidence sensitivity is unclear",
        "export request appears",
        "workflow gate bypass is requested",
    ]:
        assert term in content


def test_p20_privacy_evidence_documents_stops_guardrails_and_ci_wildcard() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")

    for term in [
        "evidence item identifier is missing",
        "privacy control area is missing",
        "source document is missing",
        "source issue or PR is missing",
        "owner is missing",
        "reviewer is missing",
        "evidence class is missing",
        "evidence sensitivity is missing",
        "retention decision is missing",
        "redaction status is missing when restricted value is suspected",
        "deletion route is missing when evidence must be replaced",
        "escalation route is missing for suspected customer data",
        "customer data export is requested",
        "private runtime value is present",
        "secret value is present",
        "raw credential is present",
        "production token is present",
        "external export is requested",
        "production launch is implied",
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

    assert "tests/integration/test_p20_step_*.py" in harness
