from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p10-step-05.md")


def test_p10_incident_drill_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p10-step-04.md",
        "docs/operations/p10-step-03.md",
        "docs/operations/p9-step-03.md",
        "docs/operations/p9-step-04.md",
        "readiness degradation is detected after controlled exposure",
    ]:
        assert term in content


def test_p10_incident_drill_documents_roles_and_timeline() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "incident commander",
        "decision owner",
        "deployment operator",
        "database operator",
        "rollback owner",
        "monitoring owner",
        "alert routing owner",
        "evidence recorder",
        "Announce simulated symptom.",
        "Review rollback decision path.",
        "End drill and publish internal notes.",
    ]:
        assert term in content


def test_p10_incident_drill_documents_escalation_and_rollback_review() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "healthcheck failure",
        "readiness failure",
        "repeated 5xx responses",
        "database connection failure",
        "migration readiness failure",
        "protected route access anomaly",
        "previous known-good image is known",
        "previous known-good configuration source is known",
        "forward-fix option is considered",
    ]:
        assert term in content


def test_p10_incident_drill_documents_evidence_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "drill date",
        "participants by role",
        "alert route result",
        "dashboard review result",
        "action items with owners",
        "drill creates real user impact",
        "live rollback is requested without explicit production decision",
        "No real user impact from the drill.",
        "No live rollback without explicit decision.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
    ]:
        assert term in content
