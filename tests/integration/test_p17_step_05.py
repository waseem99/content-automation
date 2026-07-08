from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p17-step-05.md")


def test_p17_observation_plan_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p17-step-01.md",
        "docs/operations/p17-step-02.md",
        "docs/operations/p17-step-03.md",
        "docs/operations/p17-step-04.md",
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-step-03.md",
        "docs/operations/p16-step-04.md",
        "docs/operations/p16-step-05.md",
    ]:
        assert term in content


def test_p17_observation_plan_is_observation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This plan is observation-only.",
        "approve a production launch",
        "schedule a production launch",
        "execute a production release",
        "replace go/no-go approval",
        "bypass workflow gates",
        "export customer data",
        "store secret values",
        "store private runtime values",
        "publish status pages",
        "render launch materials",
    ]:
        assert term in content


def test_p17_observation_plan_documents_windows_fields_and_statuses() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "first-hour observation window",
        "first-24-hour observation window",
        "first-7-day observation window",
        "release owner handoff",
        "operations owner handoff",
        "support owner handoff",
        "monitoring owner handoff",
        "incident owner handoff",
        "rollback owner handoff",
        "evidence owner handoff",
        "escalation owner handoff",
        "closeout review window",
        "observation item identifier",
        "observation window",
        "metric or signal",
        "watch criteria",
        "expected state",
        "observed state summary",
        "evidence sensitivity",
        "incident route",
        "escalation route",
        "rollback route",
        "action owner",
        "validation requirement",
        "closure criteria",
        "not started",
        "normal",
        "watch",
        "degraded",
        "incident triggered",
        "rollback candidate",
        "blocked",
        "needs owner",
        "needs evidence",
        "rejected with reason",
        "blocked by guardrail",
    ]:
        assert term in content


def test_p17_observation_plan_documents_watch_criteria_incidents_and_escalation() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "exact release confirmation",
        "CI baseline reference",
        "service availability signal",
        "API latency trend",
        "error-rate trend",
        "queue health trend",
        "worker success and failure trend",
        "database migration health",
        "alert volume and quality",
        "support signal volume",
        "incident channel readiness",
        "rollback trigger readiness",
        "service stability trend",
        "error recurrence trend",
        "latency recurrence trend",
        "queue backlog trend",
        "worker retry trend",
        "storage growth trend",
        "alert noise trend",
        "support ticket trend",
        "incident recurrence trend",
        "documentation correction needs",
        "follow-up action owner assignment",
        "service-level risk trend",
        "repeated incident pattern",
        "repeated alert pattern",
        "operational workload trend",
        "documentation freshness trend",
        "metrics evidence retention quality",
        "rollback readiness still-valid check",
        "improvement backlog candidates",
        "final post-release review readiness",
        "incident identifier",
        "incident owner",
        "severity level",
        "affected signal",
        "escalation owner",
        "rollback decision owner",
        "support communication owner",
        "Incident evidence must not include restricted runtime values.",
        "critical alert repeats",
        "service-level risk is breached",
        "rollback trigger is met",
        "support volume spikes materially",
        "restricted value appears in evidence",
    ]:
        assert term in content


def test_p17_observation_plan_documents_evidence_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized observation notes",
        "summarized metric trend notes",
        "summarized incident notes",
        "summarized support notes",
        "summarized rollback notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "raw logs with restricted values",
        "rendered launch materials",
        "scheduled release outputs",
        "observation owner is missing",
        "reviewer is missing",
        "evidence source is missing",
        "first-hour window is missing",
        "first-24-hour window is missing",
        "first-7-day window is missing",
        "incident route is missing",
        "escalation route is missing",
        "rollback route is missing",
        "incident owner is missing for an incident",
        "action owner is missing for required action",
        "rollback trigger has no decision owner",
        "evidence contains secret values",
        "evidence contains private runtime values",
        "evidence contains customer data exports",
        "evidence contains external package exports",
        "external export is requested",
        "workflow gate bypass is requested",
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No public production launch without explicit decision.",
        "No release without calendar entry.",
        "No release during blackout window.",
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
