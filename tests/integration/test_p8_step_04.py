from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p8-step-04.md")


def test_p8_rollback_runbook_documents_decision_points_and_roles() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Rollback decision points",
        "liveness failure",
        "readiness failure",
        "repeated 5xx responses",
        "database connection failures",
        "migration readiness failure",
        "operator workflow gate behavior changes",
        "decision owner",
        "deployment operator",
        "database operator",
        "reviewer to confirm final checks",
    ]:
        assert term in content


def test_p8_rollback_runbook_documents_app_and_config_rollback() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Application image rollback",
        "previous known-good image tag or digest",
        "compatible database schema",
        "GET /health",
        "GET /runtime/ready",
        "GET /runtime/observability",
        "Configuration rollback",
        "previous known-good configuration source",
        "GET /runtime/config",
        "No secret values are written to logs",
    ]:
        assert term in content


def test_p8_rollback_runbook_documents_database_and_traffic_safety() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Database migration safety",
        "prefer forward-fix migration when safe",
        "do not run destructive database rollback without an approved restore plan",
        "fresh current-state backup exists",
        "confirm backup checksum before restore",
        "docs/operations/p8-step-03.md",
        "Traffic handling",
        "remove unready instances from serving traffic",
        "do not route traffic to an instance with readiness failure",
        "do not bypass workflow gates to recover faster",
    ]:
        assert term in content


def test_p8_rollback_runbook_documents_verification_completion_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Post-rollback verification",
        "Confirm protected routes still require operator access.",
        "Confirm queue route can read expected data.",
        "Confirm audit route can read expected data.",
        "Rollback completion criteria",
        "service is healthy",
        "readiness is true",
        "workflow gates are not bypassed",
        "No rollback without a decision owner.",
        "No database restore without fresh backup confirmation.",
        "No secret values in logs.",
        "No private runtime values in rollback notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
        "No public production launch.",
    ]:
        assert term in content
