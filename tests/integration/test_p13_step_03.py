from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p13-step-03.md")


def test_p13_failover_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p13-step-01.md",
        "docs/operations/p13-step-02.md",
        "docs/operations/p12-step-01.md",
    ]:
        assert term in content


def test_p13_failover_documents_surfaces_prerequisites_and_owners() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "application runtime",
        "database connection",
        "migration state",
        "object storage",
        "secret access",
        "monitoring dashboard",
        "current production state",
        "backup evidence status",
        "restore validation status",
        "rollback path status",
        "failover owner",
        "rollback owner",
        "primary owner and backup owner",
    ]:
        assert term in content


def test_p13_failover_documents_decision_path_validation_and_rollback() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "decision owner approves failover review",
        "failover owner confirms prerequisites",
        "backup owner confirms backup evidence",
        "guardrail reviewer confirms no blocked condition",
        "failover review date",
        "validation method",
        "validation result",
        "rollback trigger",
        "rollback steps reference",
        "expected recovery window",
    ]:
        assert term in content


def test_p13_failover_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "failover owner is missing",
        "backup evidence is missing",
        "restore validation status is missing",
        "monitoring coverage is missing",
        "rollback path is unknown",
        "decision owner approval is missing",
        "No failover readiness closure without validation evidence.",
        "No failover decision without decision owner approval.",
        "No failover readiness without rollback path.",
        "No missing backup or restore evidence.",
        "No ownerless failover surface.",
        "No workflow gate bypass.",
    ]:
        assert term in content
