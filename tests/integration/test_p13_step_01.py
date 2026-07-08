from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p13-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p13_disaster_recovery_references_p12_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p12-readiness-report.md",
        "docs/operations/p12-closeout-checklist.md",
        "docs/operations/p12-step-04.md",
    ]:
        assert term in content


def test_p13_disaster_recovery_documents_objectives_dependencies_and_owners() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "recovery time objective",
        "recovery point objective",
        "maximum tolerated downtime",
        "maximum tolerated data loss",
        "manual operating workaround",
        "database",
        "migrations",
        "secret management",
        "alert routing",
        "disaster recovery owner",
        "restore validation owner",
        "failover owner",
        "primary owner and backup owner",
    ]:
        assert term in content


def test_p13_disaster_recovery_documents_evidence_cadence_and_decisions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "latest backup evidence",
        "latest restore evidence",
        "failover readiness status",
        "open recovery risks",
        "disaster recovery review quarterly",
        "restore validation at least quarterly",
        "tabletop review after any major incident",
        "corrective action required",
        "risk accepted with owner and expiry date",
    ]:
        assert term in content


def test_p13_disaster_recovery_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "recovery objective is missing",
        "critical dependency owner is missing",
        "backup evidence is missing",
        "restore evidence is missing",
        "failover readiness status is unknown",
        "accepted risk lacks expiry date",
        "No disaster recovery review closure without evidence.",
        "No accepted recovery risk without expiry date.",
        "No ownerless critical dependency.",
        "No missing backup evidence.",
        "No missing restore evidence.",
        "No workflow gate bypass.",
    ]:
        assert term in content


def test_p13_disaster_recovery_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p13_step_*.py" in harness
