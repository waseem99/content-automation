from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p18-step-02.md")


def test_p18_role_procedures_reference_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p18-step-01.md",
        "docs/operations/p17-readiness-report.md",
        "docs/operations/p17-step-01.md",
        "docs/operations/p17-step-02.md",
        "docs/operations/p17-step-03.md",
        "docs/operations/p17-step-04.md",
        "docs/operations/p17-step-05.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p15-readiness-report.md",
        "docs/operations/p14-step-06.md",
    ]:
        assert term in content


def test_p18_role_procedures_are_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "These procedures are documentation-only.",
        "grant production access",
        "approve production launch",
        "schedule production launch",
        "execute release activities",
        "bypass workflow gates",
        "replace manual approval",
        "publish operating material",
        "render training material",
        "export role evidence",
        "override support escalation",
    ]:
        assert term in content


def test_p18_role_procedures_document_role_catalog() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "admin",
        "reviewer",
        "operator",
        "support owner",
        "release owner",
        "incident owner",
        "evidence owner",
        "documentation owner",
    ]:
        assert term in content


def test_p18_role_procedures_document_role_specific_permissions_and_restrictions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "maintain repository settings when approved",
        "manage workflow configuration through scoped PRs",
        "bypass exact-head CI",
        "merge failing PRs",
        "billing or runner constraints block CI",
        "review scoped PRs",
        "confirm acceptance criteria",
        "approve out-of-scope changes",
        "approve unresolved blockers as completed",
        "perform daily checks",
        "monitor open issues and PRs",
        "make release decisions alone",
        "schedule launch activity",
        "triage support cases",
        "assign support action owners",
        "export customer data",
        "close support cases without evidence source",
        "manage release decision handoff",
        "confirm release calendar entry",
        "approve release from CI alone",
        "launch during blackout window",
        "classify incident severity",
        "recommend rollback decision review",
        "suppress escalation when stop condition is met",
        "validate allowed evidence types",
        "reject restricted evidence",
        "store production tokens",
        "maintain runbooks",
        "track review cadence",
        "remove guardrails",
        "hide known gaps",
    ]:
        assert term in content


def test_p18_role_procedures_document_role_record_fields_evidence_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "role identifier",
        "role name",
        "role owner",
        "reviewer",
        "allowed actions",
        "prohibited actions",
        "required escalation triggers",
        "required evidence",
        "evidence sensitivity",
        "action route",
        "stop condition",
        "validation requirement",
        "closure criteria",
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized role notes",
        "summarized reviewer notes",
        "summarized operator notes",
        "summarized support notes",
        "summarized incident notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "private environment dumps",
        "customer data exports",
        "external package exports",
        "raw logs with restricted values",
        "rendered operating materials",
        "scheduled role outputs",
        "role owner is missing",
        "allowed actions are missing",
        "prohibited actions are missing",
        "escalation triggers are missing",
        "evidence source is missing",
        "evidence sensitivity is missing",
        "automatic approval is implied",
        "production launch is implied",
        "workflow gate bypass is requested",
        "release calendar is missing for release decision",
        "blackout check is missing for release decision",
        "restricted evidence is present",
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
