from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p18-step-05.md")


def test_p18_runbook_ownership_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p14-step-01.md",
        "docs/operations/p14-step-06.md",
        "docs/operations/p15-readiness-report.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p17-readiness-report.md",
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p18-step-03.md",
        "docs/operations/p18-step-04.md",
    ]:
        assert term in content


def test_p18_runbook_ownership_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This index is documentation-only.",
        "assign live production access",
        "approve production launch",
        "schedule production launch",
        "execute review automation",
        "publish runbook material",
        "render ownership material",
        "export runbook evidence",
        "bypass workflow gates",
        "replace scoped issues and PRs",
    ]:
        assert term in content


def test_p18_runbook_ownership_documents_groups_fields_roles_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "P14 compliance and audit readiness runbooks",
        "P15 continuous improvement runbooks",
        "P16 observability and operating metrics runbooks",
        "P17 release readiness and controlled launch runbooks",
        "P18 handover and operator enablement runbooks",
        "final readiness reports",
        "closeout checklists",
        "validation tests",
        "runbook identifier",
        "runbook path",
        "phase",
        "purpose",
        "owner",
        "reviewer",
        "backup owner",
        "review cadence",
        "last review placeholder",
        "next review placeholder",
        "evidence expectation",
        "evidence sensitivity",
        "update route",
        "escalation route",
        "stale status",
        "closure criteria",
        "documentation owner",
        "operator owner",
        "support owner",
        "release owner",
        "observability owner",
        "evidence owner",
        "incident owner",
        "per PR closeout",
        "weekly during active rollout",
        "monthly during steady operation",
        "after incident",
        "after release decision",
        "after support pattern",
        "after guardrail change",
        "before phase closeout",
    ]:
        assert term in content


def test_p18_runbook_ownership_documents_routes_evidence_gaps_and_stale_handling() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "no update required",
        "update existing runbook",
        "create implementation issue",
        "create documentation issue",
        "route to evidence owner",
        "route to support owner",
        "route to release owner",
        "route to incident owner",
        "route to operator owner",
        "block by guardrail",
        "reject with reason",
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized review notes",
        "summarized update notes",
        "summarized owner notes",
        "summarized support notes",
        "summarized incident notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "raw logs with restricted values",
        "rendered runbook materials",
        "scheduled ownership outputs",
        "owner is missing",
        "reviewer is missing",
        "backup owner is missing",
        "review cadence is missing",
        "evidence expectation is missing",
        "update route is missing",
        "escalation route is missing",
        "stale status is unknown",
        "Ownership gaps must route to documentation owner before closeout.",
        "review cadence is missed",
        "referenced issue or PR is obsolete",
        "ownership no longer matches current role map",
        "guardrail language is missing",
        "evidence rules are incomplete",
        "support or incident route is outdated",
        "release-readiness dependency is outdated",
        "validation test reference is missing",
        "Stale runbooks must receive an action route before closeout.",
    ]:
        assert term in content


def test_p18_runbook_ownership_documents_minimum_map_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p18-step-03.md",
        "docs/operations/p18-step-04.md",
        "docs/operations/p18-step-05.md",
        "runbook path is missing",
        "ownership gap has no action route",
        "stale runbook has no action route",
        "validation test reference is missing",
        "automatic approval is implied",
        "production launch is implied",
        "workflow gate bypass is requested",
        "evidence contains secret values",
        "evidence contains private runtime values",
        "customer data export is requested",
        "external export is requested",
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
