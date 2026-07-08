from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p19-step-04.md")


def test_p19_supply_chain_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p19-step-01.md",
        "docs/operations/p19-step-02.md",
        "docs/operations/p19-step-03.md",
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-05.md",
        "docs/operations/p15-readiness-report.md",
        "docs/operations/p14-step-06.md",
    ]:
        assert term in content


def test_p19_supply_chain_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This supply-chain review is documentation-only.",
        "update production dependencies",
        "install new packages",
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


def test_p19_supply_chain_documents_process_policy_and_lockfile_expectations() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "dependency inventory review",
        "direct dependency identification",
        "transitive dependency awareness",
        "runtime dependency classification",
        "development dependency classification",
        "security-sensitive dependency classification",
        "package source review",
        "vulnerability signal review",
        "update route selection",
        "exact-head CI confirmation",
        "start from a scoped issue",
        "use a scoped branch from `test`",
        "describe the package and reason",
        "preserve lockfile consistency",
        "avoid unrelated dependency updates",
        "route vulnerability fixes through owner review",
        "avoid automatic merge or automatic approval",
        "lockfile path when present",
        "dependency manifest path",
        "package change summary",
        "transitive change summary",
        "validation command summary",
        "rollback route",
        "Lockfile or manifest changes require scoped PR review.",
    ]:
        assert term in content


def test_p19_supply_chain_documents_vulnerability_export_fields_actions_and_evidence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "vulnerability identifier placeholder",
        "affected dependency",
        "severity level",
        "affected scope",
        "remediation route",
        "temporary mitigation route",
        "target follow-up route",
        "informational",
        "low",
        "medium",
        "high",
        "critical",
        "High or critical findings require escalation to security incident response or a scoped implementation issue.",
        "External package export is prohibited",
        "package bundles",
        "private artifacts",
        "raw dependency archives",
        "review item identifier",
        "dependency name placeholder",
        "dependency type",
        "package source",
        "current version placeholder",
        "requested version placeholder",
        "vulnerability status",
        "lockfile status",
        "CI evidence source",
        "evidence sensitivity",
        "action route",
        "no update required",
        "update documentation only",
        "create implementation issue",
        "create security issue",
        "update dependency with scoped PR",
        "hold update with reason",
        "reject with reason",
        "escalate to security incident response",
        "block by guardrail",
        "summarized dependency notes",
        "summarized vulnerability notes",
        "summarized lockfile notes",
        "package bundle exports",
    ]:
        assert term in content


def test_p19_supply_chain_documents_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "dependency name is missing",
        "owner is missing",
        "reviewer is missing",
        "package source is missing",
        "vulnerability status is missing",
        "lockfile status is missing when lockfile is present",
        "CI evidence source is missing for dependency change",
        "high or critical finding has no escalation route",
        "package update lacks scoped issue",
        "dependency change bypasses exact-head CI",
        "automatic approval is implied",
        "external package export is requested",
        "customer data export is requested",
        "evidence contains secret values",
        "evidence contains private runtime values",
        "production launch is implied",
        "workflow gate bypass is requested",
        "No automatic approval.",
        "No automatic release.",
        "No automatic dependency approval.",
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
