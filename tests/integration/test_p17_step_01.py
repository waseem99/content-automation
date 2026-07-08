from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p17-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p17_release_decision_references_p16_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p16-closeout-checklist.md",
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-step-02.md",
        "docs/operations/p16-step-03.md",
        "docs/operations/p16-step-04.md",
        "docs/operations/p16-step-05.md",
    ]:
        assert term in content


def test_p17_release_decision_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "This phase is documentation-only.",
        "approve a production launch",
        "schedule a production launch",
        "publish a public release note",
        "render release materials",
        "export release evidence",
        "bypass workflow gates",
        "replace human approval",
    ]:
        assert term in content


def test_p17_release_decision_documents_sections_signals_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "release identifier",
        "release scope summary",
        "release candidate reference",
        "readiness summary",
        "observability readiness summary",
        "open blocker summary",
        "known risk summary",
        "dependency summary",
        "rollback readiness summary",
        "migration readiness summary",
        "monitoring readiness summary",
        "manual approval requirement",
        "go/no-go handoff summary",
        "exact-head CI status",
        "release checklist status",
        "dry-run rehearsal status",
        "alert quality status",
        "service level risk status",
        "metrics evidence status",
        "documentation freshness status",
        "incident trend status",
        "unresolved blocker status",
        "decision item identifier",
        "decision area",
        "readiness signal",
        "source evidence",
        "evidence sensitivity",
        "blocker status",
        "risk status",
        "dependency status",
        "approval requirement",
        "closure criteria",
    ]:
        assert term in content


def test_p17_release_decision_documents_statuses_routes_and_human_requirements() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "ready for review",
        "ready with notes",
        "blocked",
        "deferred",
        "needs owner",
        "needs evidence",
        "rejected with reason",
        "blocked by guardrail",
        "no action required",
        "update release decision pack",
        "update production release checklist",
        "update dry-run rehearsal process",
        "update go/no-go approval record",
        "update post-release observation plan",
        "update monitoring readiness",
        "update rollback readiness",
        "create implementation issue",
        "request more evidence",
        "named decision owner",
        "named reviewer",
        "manual go/no-go approval record",
        "rollback readiness confirmation",
        "monitoring readiness confirmation",
        "blackout check confirmation",
        "release calendar confirmation",
        "unresolved blocker disposition",
        "exact-head CI evidence",
        "Release decision pack completion does not authorize launch.",
    ]:
        assert term in content


def test_p17_release_decision_documents_evidence_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "issue or PR references",
        "CI run identifiers",
        "merge commit references",
        "summarized readiness notes",
        "summarized observability notes",
        "summarized blocker notes",
        "summarized risk notes",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "rendered release materials",
        "scheduled release outputs",
        "decision owner is missing",
        "reviewer is missing",
        "source evidence is missing",
        "manual approval requirement is missing",
        "unresolved blocker has no disposition",
        "rollback readiness is missing",
        "monitoring readiness is missing",
        "blackout check is missing",
        "calendar confirmation is missing",
        "exact-head CI evidence is missing",
        "approval is automatic",
        "public launch is implied",
        "workflow gate bypass is requested",
        "release evidence contains secret values",
        "release evidence contains private runtime values",
        "external export is requested",
        "No automatic approval.",
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


def test_p17_release_decision_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p17_step_*.py" in harness
