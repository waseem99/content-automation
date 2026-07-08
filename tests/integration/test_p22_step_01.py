from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p22-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p22_data_classification_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p21-readiness-report.md",
        "docs/operations/p20-step-01.md",
        "docs/operations/p20-step-04.md",
        "docs/operations/p19-step-03.md",
        "docs/operations/p19-step-01.md",
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-05.md",
        "docs/operations/p16-step-05.md",
    ]:
        assert term in content


def test_p22_data_classification_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This data classification and handling map is documentation-only.",
        "collect production data",
        "export customer data",
        "expose private runtime values",
        "store secret values",
        "change retention settings",
        "approve production launch",
        "schedule production launch",
        "publish data maps",
        "render data maps",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p22_data_classification_documents_classes_sensitivity_handling_and_storage() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "issue or PR reference",
        "CI run identifier",
        "merge commit reference",
        "public configuration name",
        "non-sensitive status summary",
        "summarized operator note",
        "summarized support note",
        "summarized incident note",
        "summarized audit note",
        "summarized drill note",
        "evidence archive entry name",
        "customer data",
        "private runtime value",
        "secret value",
        "raw credential",
        "production token",
        "private environment dump",
        "raw support transcript with private data",
        "screenshot containing restricted value",
        "external package export",
        "public reference",
        "internal summary",
        "restricted summary",
        "restricted value suspected",
        "restricted value confirmed",
        "customer data suspected",
        "customer data confirmed",
        "blocked by guardrail",
        "require escalation and cannot be closed without owner review",
        "allowed summary form",
        "prohibited raw form",
        "retention decision",
        "deletion or replacement route",
        "actual customer data",
        "rendered data materials",
        "scheduled data outputs",
    ]:
        assert term in content


def test_p22_data_classification_documents_roles_cadence_fields_stops_guardrails_and_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "data owner",
        "evidence owner",
        "operator owner",
        "support owner",
        "incident owner",
        "release owner",
        "documentation owner",
        "per PR closeout",
        "before privacy closeout",
        "after support pattern",
        "after incident signal",
        "after drill finding",
        "after data handling change",
        "monthly during steady operation",
        "classification item identifier",
        "data class",
        "sensitivity level",
        "source location",
        "allowed handling summary",
        "prohibited storage rule",
        "review cadence",
        "validation requirement",
        "classification item identifier is missing",
        "data class is missing",
        "sensitivity level is missing",
        "source location is missing",
        "retention decision is missing",
        "prohibited storage rule is missing",
        "escalation route is missing for restricted or customer data",
        "customer data export is requested",
        "secret value is present",
        "private runtime value is present",
        "workflow gate bypass is requested",
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No customer data exports.",
        "No external export.",
    ]:
        assert term in content

    assert "tests/integration/test_p22_step_*.py" in harness
