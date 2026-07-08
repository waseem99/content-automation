from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p15-step-04.md")


def test_p15_trend_review_references_previous_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p15-step-01.md",
        "docs/operations/p15-step-02.md",
        "docs/operations/p15-step-03.md",
        "docs/operations/p14-readiness-report.md",
    ]:
        assert term in content


def test_p15_trend_review_documents_inputs_and_categories() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "incident review notes",
        "support question patterns",
        "operational friction reports",
        "repeated alert patterns",
        "failed or delayed action tracker items",
        "manual workaround reports",
        "runbook confusion reports",
        "access review follow-up items",
        "control testing follow-up items",
        "cost and performance review actions",
        "audit readiness observations",
        "CI and validation failure patterns",
        "incident recurrence",
        "support recurrence",
        "alert recurrence",
        "manual workaround recurrence",
        "runbook gap",
        "ownership gap",
        "validation gap",
        "evidence gap",
        "access review gap",
        "control testing gap",
        "performance or cost trend",
        "product fix candidate",
    ]:
        assert term in content


def test_p15_trend_review_documents_fields_cadence_and_routing() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "trend identifier",
        "trend category",
        "source evidence",
        "first observed date",
        "latest observed date",
        "occurrence count",
        "impact summary",
        "action route",
        "action owner",
        "validation requirement",
        "evidence requirement",
        "after a material incident",
        "during monthly production improvement review",
        "before P15 closeout",
        "when repeated support patterns are observed",
        "when repeated alerts are observed",
        "update runbook",
        "create backlog item",
        "create implementation issue",
        "update alert routing",
        "update ownership record",
        "update validation evidence",
        "request more evidence",
        "accept as known limitation with owner and expiry",
        "reject with reason",
        "block by guardrail",
    ]:
        assert term in content


def test_p15_trend_review_documents_ownership_and_closure() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "trend owner",
        "reviewer",
        "action owner for routed actions",
        "validation owner when implementation is recommended",
        "evidence owner for each evidence source",
        "escalation owner for high-impact or repeated trends",
        "Critical or repeated trends cannot close without an action owner and evidence.",
        "owner and reviewer",
        "validation result when implementation occurred",
        "linked backlog item, issue, or PR when implementation occurred",
        "evidence archive entry",
        "closure decision",
        "no unresolved guardrail conflict",
    ]:
        assert term in content


def test_p15_trend_review_documents_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "source evidence is missing",
        "owner is missing",
        "reviewer is missing",
        "action route is missing",
        "action owner is missing for required action",
        "validation requirement is missing for implementation work",
        "repeated or critical trend has no action owner",
        "repeated or critical trend has no evidence",
        "item contains secret values",
        "item contains private runtime values",
        "workflow gate bypass is requested",
        "automatic approval is requested",
        "permanent exception is requested",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No critical or repeated trend closure without action owner.",
        "No critical or repeated trend closure without evidence.",
        "No permanent exceptions.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content
