from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p15-step-03.md")


def test_p15_cost_performance_references_previous_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p15-step-01.md",
        "docs/operations/p15-step-02.md",
        "docs/operations/p14-readiness-report.md",
    ]:
        assert term in content


def test_p15_cost_performance_documents_review_inputs_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "infrastructure cost signals",
        "runtime performance signals",
        "database performance signals",
        "object storage growth signals",
        "queue or worker throughput signals",
        "API latency signals",
        "error-rate trends",
        "capacity planning evidence",
        "alert noise indicators",
        "operator time spent on manual steps",
        "optimization backlog items",
        "review identifier",
        "cost owner",
        "performance owner",
        "observed trend",
        "expected impact",
        "validation requirement",
        "evidence archive entry",
    ]:
        assert term in content


def test_p15_cost_performance_documents_evidence_rules_and_decisions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "aggregated cost trend references",
        "summarized latency metrics",
        "summarized error-rate trends",
        "storage growth summaries",
        "queue and worker throughput summaries",
        "CI run identifiers",
        "issue or PR references",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "no action required",
        "optimization backlog item required",
        "implementation issue required",
        "more evidence required",
        "capacity review required",
        "documentation update required",
        "blocked by guardrail",
        "rejected with reason",
    ]:
        assert term in content


def test_p15_cost_performance_documents_ownership_action_tracking_and_closure() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "cost owner for cost-related findings",
        "performance owner for runtime findings",
        "evidence owner for each evidence source",
        "action owner for each recommended action",
        "reviewer for closure decision",
        "validation owner when implementation is recommended",
        "Ownerless findings cannot close as complete.",
        "action summary",
        "evidence required for closure",
        "linked backlog item, issue, or PR when applicable",
        "final reviewer decision",
        "evidence source is recorded",
        "validation result is recorded when implementation occurred",
        "no restricted value is included",
        "no external export is requested",
    ]:
        assert term in content


def test_p15_cost_performance_documents_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "cost owner is missing for cost finding",
        "performance owner is missing for performance finding",
        "evidence source is missing",
        "action owner is missing",
        "validation requirement is missing for implementation work",
        "item contains secret values",
        "item contains private runtime values",
        "external export is requested",
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
