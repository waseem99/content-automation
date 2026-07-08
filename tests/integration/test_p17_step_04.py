from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p17-step-04.md")


def test_p17_approval_record_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p17-step-01.md",
        "docs/operations/p17-step-02.md",
        "docs/operations/p17-step-03.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p16-step-03.md",
        "docs/operations/p16-step-04.md",
        "docs/operations/p16-step-05.md",
    ]:
        assert term in content


def test_p17_approval_record_is_manual_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This approval record is manual-only.",
        "approve a production launch by itself",
        "schedule a production launch",
        "execute a production release",
        "grant automatic approval",
        "replace named approvers",
        "bypass workflow gates",
        "ignore unresolved blockers",
        "publish release notes",
        "render launch materials",
        "export release packages",
    ]:
        assert term in content


def test_p17_approval_record_documents_sections_fields_and_statuses() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "approval record identifier",
        "release candidate reference",
        "release decision owner",
        "approver list",
        "reviewer list",
        "release checklist reference",
        "dry-run rehearsal reference",
        "exact-head CI evidence reference",
        "rollback readiness reference",
        "monitoring readiness reference",
        "blackout check reference",
        "calendar entry reference",
        "unresolved blocker summary",
        "risk acceptance summary",
        "final go/no-go status",
        "decision lock summary",
        "approval item identifier",
        "approval area",
        "required approver",
        "source evidence",
        "evidence sensitivity",
        "decision status",
        "blocker status",
        "risk status",
        "rollback status",
        "monitoring status",
        "calendar status",
        "action route",
        "validation requirement",
        "closure criteria",
        "go pending",
        "go approved",
        "no-go",
        "deferred",
        "blocked",
        "needs approver",
        "needs evidence",
        "rejected with reason",
        "blocked by guardrail",
        "A go approved status requires explicit named approval and cannot be inferred from passing CI alone.",
    ]:
        assert term in content


def test_p17_approval_record_documents_approvers_blockers_risk_and_readiness() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "technical approver",
        "operations approver",
        "rollback approver",
        "monitoring approver",
        "support approver",
        "communication approver",
        "risk acceptance approver when risk is accepted",
        "Approver placeholders cannot close as approved.",
        "blocker identifier",
        "blocker owner",
        "blocker evidence",
        "blocker impact summary",
        "blocker decision",
        "target follow-up route",
        "Unresolved blockers must result in no-go, deferred, or blocked status.",
        "risk identifier",
        "risk owner",
        "risk impact summary",
        "acceptance reason",
        "accepting approver",
        "expiry or review point",
        "rollback dependency",
        "monitoring dependency",
        "Risk cannot be accepted without a named approver, evidence, and review point.",
        "rollback owner",
        "rollback trigger",
        "rollback route",
        "rollback communication owner",
        "rollback validation requirement",
        "rollback evidence source",
        "health signal list",
        "alert routing owner",
        "service-level watch criteria",
        "post-release observation owner",
        "incident route",
        "evidence retention route",
    ]:
        assert term in content


def test_p17_approval_record_documents_decision_locks_evidence_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "required approver is missing",
        "exact-head CI evidence is missing",
        "release checklist is incomplete",
        "dry-run rehearsal is incomplete",
        "rollback readiness is missing",
        "monitoring readiness is missing",
        "blackout check is missing",
        "calendar entry is missing",
        "unresolved blocker has no disposition",
        "risk acceptance is missing approver or review point",
        "approval is automatic",
        "release evidence contains restricted values",
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized approval notes",
        "summarized blocker notes",
        "summarized risk notes",
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
        "release decision owner is missing",
        "reviewer is missing",
        "source evidence is missing",
        "release checklist reference is missing",
        "dry-run rehearsal reference is missing",
        "rollback readiness reference is missing",
        "monitoring readiness reference is missing",
        "blackout check reference is missing",
        "calendar entry reference is missing",
        "risk acceptance has no named approver",
        "risk acceptance has no review point",
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
        "No launch from approval record alone.",
        "No release without calendar entry.",
        "No release during blackout window.",
        "No unresolved blocker closure as go approved.",
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
