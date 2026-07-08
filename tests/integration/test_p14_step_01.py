from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p14-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p14_evidence_mapping_references_p13_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p13-readiness-report.md",
        "docs/operations/p13-closeout-checklist.md",
        "docs/operations/p13-step-01.md",
        "docs/operations/p13-step-02.md",
        "docs/operations/p13-step-03.md",
        "docs/operations/p13-step-04.md",
        "docs/operations/p13-step-05.md",
    ]:
        assert term in content


def test_p14_evidence_mapping_documents_categories_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "production governance evidence",
        "access review evidence",
        "security review evidence",
        "operational runbook evidence",
        "incident and action tracking evidence",
        "backup and restore evidence",
        "failover readiness evidence",
        "capacity planning evidence",
        "resilience drill evidence",
        "control testing evidence",
        "audit package evidence",
        "control objective",
        "evidence source",
        "evidence owner",
        "review owner",
        "evidence cadence",
        "readiness status",
    ]:
        assert term in content


def test_p14_evidence_mapping_documents_safe_sources_and_ownership() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "merged PR references",
        "CI run identifiers",
        "issue references",
        "evidence archive entry names",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "control owner",
        "action owner",
        "exception owner",
        "audit package owner",
        "primary owner and backup owner",
        "Ownerless evidence cannot be used to close a control.",
    ]:
        assert term in content


def test_p14_evidence_mapping_documents_cadence_states_and_stop_conditions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "compliance evidence mapping review monthly",
        "access evidence review quarterly",
        "security evidence review monthly",
        "control testing evidence review quarterly",
        "audit package evidence review before closeout",
        "ready with current evidence",
        "corrective action required",
        "evidence refresh required",
        "owner update required",
        "exception accepted with owner and expiry date",
        "blocked because evidence is missing",
        "evidence source is missing",
        "open action lacks owner",
        "accepted exception lacks expiry date",
        "external export is requested",
        "workflow gate bypass is requested",
    ]:
        assert term in content


def test_p14_evidence_mapping_documents_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "No control closure without evidence.",
        "No evidence closure without owner and review owner.",
        "No accepted exception without owner and expiry date.",
        "No access review closure with missing inventory.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No external export.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
    ]:
        assert term in content


def test_p14_evidence_mapping_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p14_step_*.py" in harness
