from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p20-step-05.md")


def test_p20_dependency_compliance_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p20-step-02.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p19-step-04.md",
        "docs/operations/p19-step-01.md",
        "docs/operations/p19-readiness-report.md",
        "docs/operations/p15-readiness-report.md",
        "docs/operations/p14-step-06.md",
    ]:
        assert term in content


def test_p20_dependency_compliance_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This dependency compliance evidence pack is documentation-only.",
        "update dependencies",
        "install packages",
        "modify lockfiles",
        "publish package artifacts",
        "export package bundles",
        "approve production launch",
        "schedule production launch",
        "bypass workflow gates",
        "replace scoped implementation issues",
        "replace exact-head CI",
    ]:
        assert term in content


def test_p20_dependency_compliance_documents_categories_fields_source_and_vulnerability_routes() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "dependency inventory review",
        "package source review",
        "direct dependency classification",
        "transitive dependency awareness",
        "runtime dependency classification",
        "development dependency classification",
        "vulnerability routing",
        "lockfile and manifest handling",
        "license or usage note review",
        "dependency change audit trail",
        "external package export restrictions",
        "evidence item identifier",
        "dependency name placeholder",
        "dependency type",
        "package source",
        "manifest path",
        "lockfile path when present",
        "current version placeholder",
        "requested version placeholder",
        "vulnerability status",
        "license or usage note status",
        "source issue or PR",
        "final head SHA when changed",
        "CI run identifiers when changed",
        "merge commit when changed",
        "evidence sensitivity",
        "action route",
        "closure criteria",
        "package source is recorded",
        "package purpose is summarized",
        "source evidence is summary-only",
        "no package bundle is exported",
        "no raw dependency archive is attached",
        "no external package export is requested",
        "no known issue recorded",
        "informational",
        "low",
        "medium",
        "high",
        "critical",
        "owner review required",
        "security incident escalation required",
        "High or critical findings require owner review and escalation before closeout.",
    ]:
        assert term in content


def test_p20_dependency_compliance_documents_lockfile_license_evidence_and_forbidden_values() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "package change summary",
        "transitive change summary",
        "validation command summary",
        "exact-head CI evidence",
        "rollback route",
        "Lockfile or manifest changes require scoped issue, scoped PR, and exact-head CI.",
        "license or usage note status",
        "escalation route when unclear",
        "This pack does not provide legal advice or approve external redistribution.",
        "issue or PR reference",
        "CI run identifier",
        "merge commit reference",
        "manifest path",
        "lockfile path",
        "summarized dependency note",
        "summarized vulnerability note",
        "summarized license or usage note",
        "summarized reviewer note",
        "evidence archive entry name",
        "external package export",
        "package bundle export",
        "raw dependency archive",
        "private package artifact",
        "secret value",
        "private runtime value",
        "raw credential",
        "production token",
        "customer data export",
        "raw log with restricted value",
    ]:
        assert term in content


def test_p20_dependency_compliance_documents_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "evidence item identifier is missing",
        "dependency name placeholder is missing",
        "dependency type is missing",
        "package source is missing",
        "owner is missing",
        "reviewer is missing",
        "source issue or PR is missing for a change",
        "final head SHA is missing for a change",
        "CI run identifier is missing for a change",
        "merge commit is missing for a change",
        "vulnerability status is missing",
        "high or critical finding has no escalation route",
        "lockfile status is missing when lockfile is present",
        "license or usage note status is missing",
        "external package export is requested",
        "package bundle export is requested",
        "customer data export is requested",
        "secret value is present",
        "private runtime value is present",
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
