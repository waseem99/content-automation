from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p13-step-05.md")


def test_p13_resilience_drill_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p13-step-01.md",
        "docs/operations/p13-step-02.md",
        "docs/operations/p13-step-03.md",
        "docs/operations/p13-step-04.md",
    ]:
        assert term in content


def test_p13_resilience_drill_documents_types_cadence_and_owners() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "disaster recovery tabletop drill",
        "backup evidence review drill",
        "restore validation drill",
        "failover readiness drill",
        "capacity threshold response drill",
        "disaster recovery tabletop quarterly",
        "backup evidence drill monthly",
        "resilience drill owner",
        "capacity planning owner",
        "primary owner and backup owner",
    ]:
        assert term in content


def test_p13_resilience_drill_documents_evidence_evaluation_and_actions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "drill ID",
        "scenario summary",
        "expected outcome",
        "actual outcome",
        "observed gaps",
        "objective completion",
        "recovery objective alignment",
        "backup and restore readiness",
        "action title",
        "validation method",
        "completion evidence",
    ]:
        assert term in content


def test_p13_resilience_drill_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "drill owner is missing",
        "required owner is missing",
        "critical gap lacks action owner",
        "action item lacks due date",
        "validation method is missing",
        "No drill closure without evidence.",
        "No critical gap without action owner.",
        "No action item without due date.",
        "No ownerless drill.",
        "No automatic approval.",
        "No workflow gate bypass.",
    ]:
        assert term in content
