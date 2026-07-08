from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p16-step-02.md")


def test_p16_dashboard_requirements_reference_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p16-step-01.md",
        "docs/operations/p15-readiness-report.md",
        "docs/operations/p15-closeout-checklist.md",
        "docs/operations/p15-step-04.md",
        "docs/operations/p15-step-05.md",
    ]:
        assert term in content


def test_p16_dashboard_requirements_are_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This phase is documentation-only.",
        "a live external dashboard",
        "a published public view",
        "scheduled reporting",
        "rendered screenshots",
        "data exports",
        "external package exports",
    ]:
        assert term in content


def test_p16_dashboard_requirements_sections_and_views() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "production health summary",
        "CI health summary",
        "workflow duration summary",
        "queue health summary",
        "worker success and failure summary",
        "retry volume summary",
        "database migration health summary",
        "latency trend summary",
        "storage growth summary",
        "error-rate summary",
        "alert volume and quality summary",
        "service level review summary",
        "support and incident trend summary",
        "documentation freshness summary",
        "action backlog summary",
        "daily operator review",
        "release readiness review",
        "incident follow-up review",
        "weekly operations review",
        "monthly production health review",
        "phase closeout review",
    ]:
        assert term in content


def test_p16_dashboard_requirements_fields_and_display_rules() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "section identifier",
        "section purpose",
        "metric references",
        "refresh expectation",
        "evidence sensitivity",
        "review cadence",
        "action route",
        "stop condition",
        "closure criteria",
        "status label",
        "trend direction",
        "summarized count",
        "summarized duration",
        "summarized error rate",
        "summarized queue depth",
        "linked issue or PR reference",
        "linked evidence archive entry",
        "raw credentials",
        "secret values",
        "private runtime values",
        "customer data exports",
        "private environment dumps",
        "external dashboard URLs created by this phase",
        "rendered images",
        "scheduled report outputs",
    ]:
        assert term in content


def test_p16_dashboard_requirements_actions_ownership_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "before release readiness review",
        "after material incident",
        "update metric catalog",
        "update dashboard requirement",
        "create implementation issue",
        "update alert quality review",
        "update service level review",
        "update metrics evidence retention",
        "update documentation freshness review",
        "request more evidence",
        "blocked by guardrail",
        "rejected with reason",
        "dashboard section owner",
        "evidence owner",
        "action owner when action is required",
        "validation owner when implementation is recommended",
        "escalation owner for missing or misleading operator visibility",
        "Ownerless dashboard sections cannot close as reviewed.",
        "dashboard section owner is missing",
        "reviewer is missing",
        "evidence source is missing",
        "metric reference is missing",
        "review cadence is missing",
        "action owner is missing for required action",
        "requirement asks for publishing",
        "requirement asks for scheduling",
        "requirement asks for rendering",
        "requirement asks for external export",
        "requirement includes secret values",
        "requirement includes private runtime values",
        "workflow gate bypass is requested",
        "automatic approval is requested",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
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
