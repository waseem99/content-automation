from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p16-step-03.md")


def test_p16_alert_quality_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-step-02.md",
        "docs/operations/p15-step-04.md",
        "docs/operations/p15-step-05.md",
        "docs/operations/p15-readiness-report.md",
    ]:
        assert term in content


def test_p16_alert_quality_documents_categories_and_severity() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "actionable alert",
        "false positive",
        "duplicate alert",
        "noisy threshold",
        "missing owner",
        "missing evidence",
        "routing gap",
        "severity mismatch",
        "repeated alert pattern",
        "service level risk",
        "documentation gap",
        "implementation candidate",
        "blocked by guardrail",
        "informational",
        "low",
        "medium",
        "high",
        "critical",
        "observable impact",
        "repeat frequency",
        "operator action need",
        "service-level risk",
        "evidence availability",
    ]:
        assert term in content


def test_p16_alert_quality_documents_required_fields_and_routing() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "alert identifier",
        "alert category",
        "severity level",
        "source signal",
        "first observed date",
        "latest observed date",
        "occurrence count",
        "routing destination",
        "evidence sensitivity",
        "action owner",
        "validation requirement",
        "closure decision",
        "primary owner",
        "backup owner",
        "escalation owner",
        "response expectation",
        "follow-up route",
        "evidence reference",
        "Critical or repeated alert patterns require an action owner and evidence.",
    ]:
        assert term in content


def test_p16_alert_quality_documents_false_positive_handling_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "why the alert was false positive",
        "affected metric",
        "threshold review decision",
        "routing review decision",
        "action owner when tuning is required",
        "False-positive closure cannot remove controls without scoped issue, PR, and exact-head CI.",
        "after material incident",
        "when repeated alerts appear",
        "when false positives repeat",
        "during weekly operations review",
        "during monthly production health review",
        "before phase closeout",
    ]:
        assert term in content


def test_p16_alert_quality_documents_actions_ownership_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "no action required",
        "update alert threshold",
        "update alert routing",
        "update metric catalog",
        "update service level review",
        "update dashboard requirement",
        "update documentation freshness review",
        "create implementation issue",
        "request more evidence",
        "reject with reason",
        "block by guardrail",
        "alert owner",
        "evidence owner",
        "routing owner",
        "validation owner when implementation is recommended",
        "escalation owner for critical or repeated alert patterns",
        "Ownerless alert review items cannot close as reviewed.",
        "alert owner is missing",
        "reviewer is missing",
        "evidence source is missing",
        "severity level is missing",
        "routing destination is missing",
        "repeated alert has no action owner",
        "critical alert has no action owner",
        "false-positive decision has no evidence",
        "action owner is missing for required action",
        "validation requirement is missing for implementation",
        "alert evidence includes secret values",
        "alert evidence includes private runtime values",
        "workflow gate bypass is requested",
        "automatic approval is requested",
        "external export is requested",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No control removal without scoped issue, PR, and validation.",
        "No critical or repeated alert closure without action owner.",
        "No critical or repeated alert closure without evidence.",
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
