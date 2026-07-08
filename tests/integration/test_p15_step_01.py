from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p15-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p15_improvement_backlog_references_p14_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p14-readiness-report.md",
        "docs/operations/p14-closeout-checklist.md",
        "docs/operations/p14-step-01.md",
        "docs/operations/p14-step-02.md",
        "docs/operations/p14-step-03.md",
        "docs/operations/p14-step-04.md",
        "docs/operations/p14-step-05.md",
    ]:
        assert term in content


def test_p15_improvement_backlog_documents_categories_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "recurring operational friction",
        "manual production steps",
        "reliability improvement opportunities",
        "alert quality improvements",
        "runbook usability improvements",
        "evidence collection improvements",
        "access review improvements",
        "control testing improvements",
        "cost optimization opportunities",
        "performance optimization opportunities",
        "support and incident trend actions",
        "documentation freshness actions",
        "item identifier",
        "problem statement",
        "expected improvement",
        "source evidence",
        "validation requirement",
        "closure evidence",
    ]:
        assert term in content


def test_p15_improvement_backlog_documents_intake_and_triage() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "production review notes",
        "incident review actions",
        "support trend review",
        "operator feedback",
        "CI and validation evidence",
        "audit readiness findings",
        "runbook freshness review",
        "cost or performance review",
        "alert routing review",
        "confirm the problem statement",
        "confirm source evidence",
        "assign owner and reviewer",
        "classify category, priority, and risk",
        "confirm whether implementation requires an issue",
        "confirm validation requirement",
        "confirm no guardrail conflict",
    ]:
        assert term in content


def test_p15_improvement_backlog_documents_statuses_ownership_and_closure() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "needs evidence",
        "blocked by guardrail",
        "implementation issue required",
        "validation pending",
        "complete with evidence",
        "rejected with reason",
        "each accepted item has an owner",
        "each accepted item has a reviewer",
        "validation owner",
        "escalation owner",
        "blocker owner",
        "Ownerless improvement items cannot move to accepted, in progress, or complete.",
        "linked evidence source",
        "final decision",
        "validation result when implementation occurred",
        "linked issue or PR when implementation occurred",
        "no unresolved guardrail conflict",
    ]:
        assert term in content


def test_p15_improvement_backlog_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "source evidence is missing",
        "owner is missing",
        "reviewer is missing",
        "validation requirement is missing for implementation work",
        "linked issue or PR is missing for implementation work",
        "closure evidence is missing",
        "item requires automatic approval",
        "item requires workflow gate bypass",
        "item requires publishing, scheduling, rendering, or external export",
        "item contains secret values",
        "item contains private runtime values",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No public production launch without explicit decision.",
        "No release without calendar entry.",
        "No release during blackout window.",
        "No control closure without evidence.",
        "No access review closure with missing inventory.",
        "No permanent exceptions.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content


def test_p15_improvement_backlog_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p15_step_*.py" in harness
