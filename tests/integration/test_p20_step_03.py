from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p20-step-03.md")


def test_p20_audit_trail_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p20-step-01.md",
        "docs/operations/p20-step-02.md",
        "docs/operations/p19-readiness-report.md",
        "docs/operations/p18-readiness-report.md",
        "docs/operations/p17-readiness-report.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p15-readiness-report.md",
    ]:
        assert term in content


def test_p20_audit_trail_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This audit trail review is documentation-only.",
        "approve production launch",
        "schedule production launch",
        "merge changes",
        "bypass workflow gates",
        "alter branch protection",
        "create audit exports",
        "publish audit evidence",
        "render audit evidence",
        "replace exact-head CI",
        "replace scoped issues and PRs",
    ]:
        assert term in content


def test_p20_audit_trail_documents_components_fields_and_traceability() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "parent epic",
        "scoped child issue",
        "branch created from `test`",
        "PR with exact title and body format",
        "changed files list",
        "final PR head SHA",
        "required exact-head CI run identifiers",
        "merge commit reference",
        "issue closure confirmation",
        "parent epic closeout evidence",
        "readiness report",
        "closeout checklist",
        "validation test",
        "change evidence identifier",
        "parent epic number",
        "child issue number",
        "branch name",
        "PR number",
        "PR title",
        "PR body status",
        "final head SHA",
        "required CI run identifiers",
        "CI conclusion",
        "merge commit",
        "issue closure status",
        "evidence sensitivity",
        "closure criteria",
        "every implementation has a scoped issue",
        "every implementation branch starts from `test`",
        "every PR closes the scoped issue",
        "every PR uses the required title format",
        "every PR uses the required body format",
        "every final merge uses the final exact head",
        "every required check is green on the final exact head",
        "every issue closes after merge",
        "every epic closes only after final closeout evidence",
    ]:
        assert term in content


def test_p20_audit_trail_documents_checks_exceptions_and_evidence_rules() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "No merge or closeout may be treated as valid without exact-head CI evidence.",
        "exception identifier",
        "affected issue or PR",
        "exception owner",
        "business reason summary",
        "expiry or review point",
        "compensating control",
        "Exceptions cannot bypass required CI, scoped issue workflow, or restricted evidence guardrails.",
        "issue or PR reference",
        "branch name",
        "final head SHA",
        "CI run identifier",
        "merge commit reference",
        "summarized review note",
        "summarized closeout note",
        "readiness report path",
        "closeout checklist path",
        "validation test path",
        "secret value",
        "private runtime value",
        "raw credential",
        "production token",
        "customer data export",
        "external package export",
        "raw log with restricted value",
        "rendered audit material",
        "scheduled audit output",
    ]:
        assert term in content


def test_p20_audit_trail_documents_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "parent epic number is missing",
        "child issue number is missing",
        "branch name is missing",
        "PR number is missing",
        "final head SHA is missing",
        "required CI run identifier is missing",
        "CI conclusion is not success",
        "merge commit is missing",
        "issue closure status is missing",
        "owner is missing",
        "reviewer is missing",
        "exact-head CI evidence is missing",
        "scoped issue linkage is missing",
        "exception attempts to bypass CI",
        "secret value is present",
        "private runtime value is present",
        "customer data export is requested",
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
