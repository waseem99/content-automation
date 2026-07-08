from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p16-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p16_health_metrics_references_p15_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p15-readiness-report.md",
        "docs/operations/p15-closeout-checklist.md",
        "docs/operations/p15-step-01.md",
        "docs/operations/p15-step-03.md",
        "docs/operations/p15-step-04.md",
        "docs/operations/p15-step-05.md",
    ]:
        assert term in content


def test_p16_health_metrics_documents_core_signals_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "CI health",
        "workflow duration",
        "workflow failure rate",
        "queue health",
        "worker success rate",
        "worker failure rate",
        "retry volume",
        "database migration health",
        "database latency trend",
        "API latency trend",
        "storage growth trend",
        "object processing volume",
        "error-rate trend",
        "alert volume trend",
        "support trend volume",
        "incident recurrence trend",
        "documentation freshness trend",
        "operator manual effort trend",
        "metric identifier",
        "signal source",
        "review cadence",
        "threshold or review trigger",
        "evidence sensitivity",
        "retention reference",
    ]:
        assert term in content


def test_p16_health_metrics_documents_cadence_and_evidence_rules() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "per pull request",
        "per release readiness review",
        "weekly operations review",
        "monthly production health review",
        "after material incident",
        "before phase closeout",
        "Every metric must have one cadence and one owner.",
        "CI run identifiers",
        "summarized workflow duration notes",
        "summarized queue health notes",
        "summarized worker success or failure notes",
        "summarized latency trends",
        "summarized error-rate trends",
        "summarized storage growth notes",
        "issue or PR references",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
    ]:
        assert term in content


def test_p16_health_metrics_documents_action_routes_and_ownership() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "no action required",
        "operational improvement backlog",
        "alert quality review",
        "service level review",
        "metrics evidence retention review",
        "documentation freshness review",
        "implementation issue required",
        "more evidence required",
        "blocked by guardrail",
        "rejected with reason",
        "metric owner",
        "evidence owner",
        "action owner when action is required",
        "validation owner when implementation is recommended",
        "escalation owner for repeated or high-impact degradation",
        "Ownerless metrics cannot close as reviewed.",
    ]:
        assert term in content


def test_p16_health_metrics_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "metric owner is missing",
        "reviewer is missing",
        "signal source is missing",
        "evidence source is missing",
        "review cadence is missing",
        "threshold or review trigger is missing",
        "action owner is missing for required action",
        "metric contains secret values",
        "metric contains private runtime values",
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


def test_p16_health_metrics_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p16_step_*.py" in harness
