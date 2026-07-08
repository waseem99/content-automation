from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p16-step-05.md")


def test_p16_metrics_retention_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-step-02.md",
        "docs/operations/p16-step-03.md",
        "docs/operations/p16-step-04.md",
        "docs/operations/p15-step-05.md",
        "docs/operations/p15-readiness-report.md",
    ]:
        assert term in content


def test_p16_metrics_retention_documents_scope_and_allowed_evidence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "CI run evidence",
        "workflow duration evidence",
        "queue health evidence",
        "worker success and failure evidence",
        "retry volume evidence",
        "database migration health evidence",
        "latency trend evidence",
        "storage growth evidence",
        "error-rate evidence",
        "alert quality evidence",
        "service-level review evidence",
        "support and incident trend evidence",
        "documentation freshness evidence",
        "phase closeout evidence",
        "CI run identifier",
        "summarized metric trend",
        "summarized workflow duration note",
        "summarized queue health note",
        "summarized incident note",
        "summarized alert quality note",
        "summarized service-level note",
        "issue or PR reference",
        "merge commit reference",
        "evidence archive entry name",
        "owner review note",
    ]:
        assert term in content


def test_p16_metrics_retention_documents_exclusions_fields_and_classifications() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "private environment dumps",
        "customer data exports",
        "external package exports",
        "raw logs with restricted values",
        "rendered dashboards",
        "scheduled report outputs",
        "public status pages created by this phase",
        "evidence identifier",
        "metric reference",
        "evidence type",
        "source reference",
        "sensitivity classification",
        "retention decision",
        "retention reference",
        "review cadence",
        "action route",
        "validation requirement",
        "closure criteria",
        "public reference",
        "internal summary",
        "restricted summary",
        "blocked restricted value",
        "customer data risk",
        "secret value risk",
        "private runtime risk",
        "external export risk",
    ]:
        assert term in content


def test_p16_metrics_retention_documents_decisions_cadence_and_actions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "retain reference",
        "retain summary",
        "rotate summary",
        "archive reference",
        "needs owner",
        "needs reviewer",
        "needs evidence",
        "remove restricted value",
        "reject with reason",
        "block by guardrail",
        "before phase closeout",
        "during monthly production health review",
        "after material incident",
        "after service-level review updates",
        "after alert quality review updates",
        "after documentation freshness review updates",
        "when metric evidence changes",
        "no action required",
        "update retained summary",
        "update evidence owner",
        "update evidence reference",
        "update sensitivity classification",
        "update metric catalog",
        "update documentation freshness review",
        "create implementation issue",
        "request more evidence",
    ]:
        assert term in content


def test_p16_metrics_retention_documents_ownership_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "evidence owner",
        "metric owner",
        "retention owner",
        "action owner when action is required",
        "validation owner when implementation is recommended",
        "escalation owner for restricted value risk or external export risk",
        "Ownerless retained evidence cannot close as reviewed.",
        "evidence owner is missing",
        "reviewer is missing",
        "metric reference is missing",
        "source reference is missing",
        "sensitivity classification is missing",
        "retention decision is missing",
        "retention reference is missing",
        "action owner is missing for required action",
        "validation requirement is missing for implementation",
        "evidence contains secret values",
        "evidence contains private runtime values",
        "evidence contains customer data exports",
        "evidence contains external package exports",
        "evidence requires publishing",
        "evidence requires scheduling",
        "evidence requires rendering",
        "evidence requires external export",
        "workflow gate bypass is requested",
        "automatic approval is requested",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No retained secret values.",
        "No retained private runtime values.",
        "No customer data exports.",
        "No external package exports.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content
