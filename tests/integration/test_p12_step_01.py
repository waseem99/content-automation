from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p12-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p12_release_calendar_references_p11_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p11-readiness-report.md",
        "docs/operations/p11-closeout-checklist.md",
        "docs/operations/p11-step-05.md",
    ]:
        assert term in content


def test_p12_release_calendar_documents_ownership_and_windows() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "release calendar owner",
        "decision owner",
        "deployment owner",
        "rollback owner",
        "monitoring owner",
        "evidence archive owner",
        "primary owner and backup owner",
        "release date",
        "affected surface",
        "readiness evidence link",
        "rollback readiness link",
        "evidence archive entry",
    ]:
        assert term in content


def test_p12_release_calendar_documents_blackouts_readiness_and_change_records() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Blackout windows must be recorded",
        "active incidents",
        "unresolved rollback gaps",
        "Release expansion is not allowed during a blackout window.",
        "release calendar entry",
        "deployment checklist status",
        "open exception status",
        "change ID",
        "linked issue or PR",
        "final outcome",
    ]:
        assert term in content


def test_p12_release_calendar_documents_approval_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "decision owner approves the release window",
        "rollback owner confirms rollback path",
        "guardrail reviewer confirms no blocked condition",
        "blackout window is active",
        "workflow gate bypass is requested",
        "No release without calendar entry.",
        "No release during blackout window.",
        "No release without decision owner approval.",
        "No release without rollback readiness.",
        "No automatic approval.",
    ]:
        assert term in content


def test_p12_release_calendar_adds_ci_wildcard() -> None:
    harness = HARNESS.read_text(encoding="utf-8")

    assert "tests/integration/test_p12_step_*.py" in harness
