from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p17-step-02.md")


def test_p17_release_checklist_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p17-step-01.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-step-03.md",
        "docs/operations/p16-step-04.md",
        "docs/operations/p16-step-05.md",
    ]:
        assert term in content


def test_p17_release_checklist_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This checklist is documentation-only.",
        "approve a production launch",
        "schedule a production launch",
        "execute a production release",
        "publish release notes",
        "render launch materials",
        "export release packages",
        "bypass workflow gates",
        "replace explicit human confirmation",
    ]:
        assert term in content


def test_p17_release_checklist_documents_sections_fields_and_statuses() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "release candidate check",
        "environment readiness check",
        "configuration readiness check",
        "secrets handling check",
        "migration readiness check",
        "rollback readiness check",
        "monitoring readiness check",
        "alert readiness check",
        "support readiness check",
        "documentation readiness check",
        "calendar entry check",
        "blackout window check",
        "communication readiness check",
        "evidence retention check",
        "final manual confirmation check",
        "checklist item identifier",
        "checklist section",
        "check description",
        "expected evidence",
        "evidence source",
        "evidence sensitivity",
        "blocker status",
        "action route",
        "validation requirement",
        "closure criteria",
        "not started",
        "ready",
        "ready with notes",
        "blocked",
        "not applicable with reason",
        "needs owner",
        "needs evidence",
        "rejected with reason",
        "blocked by guardrail",
    ]:
        assert term in content


def test_p17_release_checklist_documents_environment_rollback_monitoring_and_calendar_rules() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "target environment is named",
        "release candidate is identified",
        "required configuration is reviewed",
        "secrets handling is reviewed without recording secret values",
        "migration path is reviewed",
        "rollback route is identified",
        "monitoring signals are defined",
        "release owners are named",
        "release calendar entry is present",
        "blackout window is checked",
        "rollback owner",
        "rollback trigger",
        "rollback route",
        "rollback evidence source",
        "rollback communication owner",
        "rollback validation requirement",
        "Release cannot be marked ready without rollback readiness.",
        "health signal list",
        "alert routing owner",
        "service-level watch criteria",
        "post-release observation owner",
        "incident route",
        "evidence retention route",
        "Release cannot be marked ready without monitoring readiness.",
        "release calendar entry",
        "release window owner",
        "blackout window check",
        "communication owner",
        "decision owner",
        "go/no-go record reference",
        "No release may proceed during a blackout window.",
    ]:
        assert term in content


def test_p17_release_checklist_documents_evidence_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized readiness notes",
        "summarized configuration review notes",
        "summarized migration review notes",
        "summarized rollback notes",
        "summarized monitoring notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "rendered release materials",
        "scheduled release outputs",
        "owner is missing",
        "reviewer is missing",
        "evidence source is missing",
        "release candidate is missing",
        "target environment is missing",
        "rollback readiness is missing",
        "monitoring readiness is missing",
        "calendar entry is missing",
        "blackout check is missing",
        "go/no-go record reference is missing",
        "automatic release is implied",
        "public launch is implied",
        "workflow gate bypass is requested",
        "evidence contains secret values",
        "evidence contains private runtime values",
        "external export is requested",
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No public production launch without explicit decision.",
        "No release without calendar entry.",
        "No release during blackout window.",
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
