from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p11-step-05.md")


def test_p11_operator_handoff_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p11-step-01.md",
        "docs/operations/p11-step-02.md",
        "docs/operations/p11-step-03.md",
        "docs/operations/p11-step-04.md",
        "docs/operations/p10-step-01.md",
    ]:
        assert term in content


def test_p11_operator_handoff_documents_matrix_and_package() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "decision owner",
        "operations owner",
        "deployment owner",
        "database owner",
        "monitoring owner",
        "alert routing owner",
        "incident review owner",
        "evidence archive owner",
        "rollback owner",
        "primary owner and backup owner",
        "current rollout status",
        "current exposure boundary",
        "known limitations",
        "escalation contacts",
    ]:
        assert term in content


def test_p11_operator_handoff_documents_steps_escalation_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Outgoing owner prepares handoff package.",
        "Incoming owner reviews open actions and risks.",
        "Decision owner records handoff acceptance.",
        "primary and backup owner are both unavailable",
        "ownership change is not accepted by decision owner",
        "weekly during stabilization",
        "after any incident review",
        "before any exposure expansion",
        "before P11 closeout",
    ]:
        assert term in content


def test_p11_operator_handoff_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "required owner is missing",
        "backup owner is missing",
        "decision owner has not accepted handoff",
        "active incident lacks owner",
        "No ownerless production action.",
        "No handoff without decision owner acceptance.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
    ]:
        assert term in content
