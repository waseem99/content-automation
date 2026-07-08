from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p10-step-03.md")


def test_p10_controlled_exposure_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p10-step-01.md",
        "docs/operations/p10-step-02.md",
        "docs/operations/p9-step-05.md",
        "approved production exposure decision record exists",
        "deployment execution checklist is complete",
        "rollback owner is available",
        "alert route is available",
    ]:
        assert term in content


def test_p10_controlled_exposure_documents_window_and_smoke_tests() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "start time",
        "planned end time",
        "allowed audience or access boundary",
        "rollback trigger threshold",
        "GET /health",
        "GET /runtime/ready",
        "GET /runtime/config",
        "GET /runtime/observability",
        "protected routes reject unauthenticated access",
        "authenticated operator can read queue view",
        "authenticated operator can read dashboard queue view",
        "authenticated operator can read audit view",
    ]:
        assert term in content


def test_p10_controlled_exposure_documents_rollback_triggers_and_hold_points() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "health check fails",
        "readiness check fails",
        "protected route access is not enforced",
        "repeated 5xx responses exceed threshold",
        "queue route fails unexpectedly",
        "audit route fails unexpectedly",
        "before enabling exposure",
        "after smoke test completion",
        "before expanding beyond initial access boundary",
        "Each hold point requires human acknowledgement.",
    ]:
        assert term in content


def test_p10_controlled_exposure_documents_evidence_and_stop_conditions() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "decision record reference",
        "deployment checklist reference",
        "smoke test results",
        "dashboard signal result",
        "rollback trigger review result",
        "decision record is missing",
        "deployment checklist is incomplete",
        "any required smoke test fails",
        "workflow gate bypass is requested",
        "Do not record secrets, tokens, connection strings, raw operator keys, or private runtime values.",
    ]:
        assert term in content


def test_p10_controlled_exposure_preserves_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "No exposure without approved decision record.",
        "No exposure expansion without smoke test pass.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content
