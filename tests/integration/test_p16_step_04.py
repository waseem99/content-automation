from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p16-step-04.md")


def test_p16_service_level_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-step-02.md",
        "docs/operations/p16-step-03.md",
        "docs/operations/p15-step-03.md",
        "docs/operations/p15-step-04.md",
    ]:
        assert term in content


def test_p16_service_level_is_internal_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This process is internal",
        "public service level commitments",
        "public launch decisions",
        "external status pages",
        "published reports",
        "scheduled reporting",
        "rendered dashboards",
        "exported evidence packages",
    ]:
        assert term in content


def test_p16_service_level_documents_targets_fields_and_statuses() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "CI completion health",
        "workflow duration",
        "queue processing health",
        "worker completion health",
        "retry containment",
        "database migration health",
        "API latency trend",
        "error-rate trend",
        "alert response quality",
        "incident recurrence",
        "storage growth review",
        "documentation freshness",
        "service-level identifier",
        "target area",
        "target description",
        "measurement window",
        "metric source",
        "evidence sensitivity",
        "target status",
        "breach status",
        "action owner",
        "validation requirement",
        "within target",
        "watch",
        "degraded",
        "breached",
        "insufficient evidence",
        "blocked by guardrail",
    ]:
        assert term in content


def test_p16_service_level_documents_breach_review_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "breach identifier",
        "affected target",
        "observed signal",
        "impact summary",
        "source evidence",
        "follow-up route",
        "closure decision",
        "Breach findings require an owner, evidence, and follow-up route.",
        "Critical or repeated breach findings require an action owner and validation requirement.",
        "before release readiness review",
        "after material incident",
        "when repeated alerts indicate service-level risk",
        "during weekly operations review",
        "during monthly production health review",
        "before phase closeout",
    ]:
        assert term in content


def test_p16_service_level_documents_actions_evidence_ownership_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "no action required",
        "monitor next review",
        "update metric catalog",
        "update dashboard requirement",
        "update alert quality review",
        "update support and incident trend review",
        "update documentation freshness review",
        "create implementation issue",
        "request more evidence",
        "reject with reason",
        "block by guardrail",
        "CI run identifiers",
        "summarized metric trends",
        "summarized incident notes",
        "summarized alert quality notes",
        "issue or PR references",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "customer data exports",
        "external package exports",
        "service-level owner",
        "breach owner when breached",
        "validation owner when implementation is recommended",
        "escalation owner for critical or repeated breach findings",
        "Ownerless service-level items cannot close as reviewed.",
        "service-level owner is missing",
        "reviewer is missing",
        "metric source is missing",
        "evidence source is missing",
        "target status is missing",
        "breach has no owner",
        "breach has no evidence",
        "breach has no follow-up route",
        "critical or repeated breach has no action owner",
        "validation requirement is missing for implementation",
        "service-level evidence includes secret values",
        "service-level evidence includes private runtime values",
        "public launch decision is requested",
        "workflow gate bypass is requested",
        "automatic approval is requested",
        "external export is requested",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No public production launch without explicit decision.",
        "No public service-level commitment from this phase.",
        "No breach closure without owner, evidence, and follow-up route.",
        "No critical or repeated breach closure without action owner.",
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
