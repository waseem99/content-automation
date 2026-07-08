from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p18-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p18_operator_handover_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p14-step-01.md",
        "docs/operations/p14-step-06.md",
        "docs/operations/p15-readiness-report.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p17-readiness-report.md",
        "docs/operations/p17-step-01.md",
        "docs/operations/p17-step-02.md",
        "docs/operations/p17-step-03.md",
        "docs/operations/p17-step-04.md",
        "docs/operations/p17-step-05.md",
    ]:
        assert term in content


def test_p18_operator_handover_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This guide is documentation-only.",
        "approve production launch",
        "schedule production launch",
        "execute release activities",
        "grant automatic approval",
        "bypass workflow gates",
        "publish operator material",
        "render training material",
        "export handover evidence",
        "replace role-based procedures",
        "replace support escalation",
    ]:
        assert term in content


def test_p18_operator_handover_documents_orientation_context_and_principles() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "current phase context",
        "parent epic and child issue workflow",
        "branch naming rules",
        "PR title and body rules",
        "exact-head CI requirement",
        "release calendar requirement",
        "blackout window requirement",
        "manual approval requirement",
        "evidence safety rules",
        "escalation routes",
        "production compliance context",
        "continuous improvement context",
        "observability context",
        "release readiness context",
        "current open issue list",
        "current open PR list",
        "latest readiness report",
        "latest closeout checklist",
        "latest exact-head CI evidence",
        "active guardrails",
        "work from a scoped issue",
        "create a branch from `test`",
        "use exact PR title and body format",
        "wait for exact-head CI",
        "patch failures on the same branch",
        "confirm issue closure after merge",
        "never store restricted values in evidence",
    ]:
        assert term in content


def test_p18_operator_handover_documents_daily_checks_evidence_and_escalation() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "open issues review",
        "open PR review",
        "required workflow status review",
        "failed CI review",
        "blocked issue review",
        "evidence sensitivity review",
        "support signal review",
        "incident signal review",
        "documentation freshness review",
        "next-action owner review",
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized operator notes",
        "summarized support notes",
        "summarized incident notes",
        "summarized readiness notes",
        "summarized closeout notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "raw logs with restricted values",
        "rendered operator materials",
        "scheduled handover outputs",
        "exact-head CI fails",
        "issue scope is unclear",
        "PR scope expands",
        "release decision is requested",
        "blackout window conflict appears",
        "manual approval is missing",
        "workflow gate bypass is requested",
    ]:
        assert term in content


def test_p18_operator_handover_documents_fields_actions_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "handover item identifier",
        "handover area",
        "required context",
        "operator owner",
        "reviewer",
        "evidence source",
        "evidence sensitivity",
        "daily check requirement",
        "escalation route",
        "action route",
        "validation requirement",
        "closure criteria",
        "no action required",
        "update operator handover guide",
        "update role-based procedure",
        "update training checklist",
        "update support playbook",
        "update runbook ownership map",
        "create implementation issue",
        "request more evidence",
        "escalate to release owner",
        "escalate to support owner",
        "block by guardrail",
        "reject with reason",
        "operator owner is missing",
        "reviewer is missing",
        "required context is missing",
        "evidence source is missing",
        "escalation route is missing",
        "daily checks are missing",
        "action owner is missing for required action",
        "exact-head CI evidence is missing for implementation",
        "release approval is implied",
        "production launch is implied",
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


def test_p18_operator_handover_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p18_step_*.py" in harness
