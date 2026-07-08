from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p15-step-02.md")


def test_p15_automation_review_references_previous_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p15-step-01.md",
        "docs/operations/p14-readiness-report.md",
        "docs/operations/p14-closeout-checklist.md",
    ]:
        assert term in content


def test_p15_automation_review_documents_candidate_categories_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "evidence collection assistance",
        "runbook consistency checks",
        "documentation freshness checks",
        "alert triage assistance",
        "operational checklist preparation",
        "cost and performance signal aggregation",
        "support trend grouping",
        "incident action tracking reminders",
        "validation evidence summarization",
        "backlog hygiene checks",
        "candidate identifier",
        "manual step being reduced",
        "expected benefit",
        "approval boundary",
        "stop condition review",
    ]:
        assert term in content


def test_p15_automation_review_documents_risk_review_and_scoring() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "whether the automation could approve work automatically",
        "whether the automation could bypass workflow gates",
        "whether the automation could publish, schedule, render, or externally export content",
        "whether the automation could expose secret values",
        "whether the automation could expose private runtime values",
        "whether a human reviewer remains in the decision path",
        "manual effort reduced",
        "repeat frequency",
        "operational risk",
        "review complexity",
        "validation complexity",
        "evidence sensitivity",
        "rollback simplicity",
        "owner availability",
    ]:
        assert term in content


def test_p15_automation_review_documents_recommendations_and_approval_boundary() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "recommend implementation issue",
        "recommend manual process only",
        "recommend more evidence",
        "recommend blocked by guardrail",
        "recommend reject with reason",
        "Automation review can only recommend next action.",
        "approve the automation",
        "merge implementation",
        "bypass CI",
        "bypass human review",
        "bypass release calendar controls",
        "create production launch approval",
        "Any implementation still requires a scoped issue, branch, PR, exact-head CI, and merge approval under the existing workflow.",
    ]:
        assert term in content


def test_p15_automation_review_documents_ownership_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "candidate owner",
        "security reviewer when sensitive evidence is involved",
        "validation owner when implementation is recommended",
        "Ownerless candidates cannot be recommended for implementation.",
        "candidate owner is missing",
        "approval boundary is missing",
        "validation owner is missing for implementation recommendation",
        "candidate could approve work automatically",
        "candidate could bypass workflow gates",
        "candidate could publish, schedule, render, or externally export content",
        "candidate could expose secret values",
        "candidate could expose private runtime values",
        "exception has no owner or expiry date",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No public production launch without explicit decision.",
        "No release without calendar entry.",
        "No release during blackout window.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No permanent exceptions.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content
