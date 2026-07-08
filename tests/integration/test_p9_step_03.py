from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p9-step-03.md")


def test_p9_rollback_rehearsal_references_prior_runbooks() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p8-step-04.md",
        "docs/operations/p9-step-01.md",
        "docs/operations/p9-step-02.md",
        "rollback role confirmation",
        "rollback decision point review",
        "traffic isolation rehearsal",
    ]:
        assert term in content


def test_p9_rollback_rehearsal_documents_preparation_and_decision_points() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "previous known-good image tag or digest",
        "previous known-good configuration source",
        "restore rehearsal evidence is available",
        "rollback owner is available",
        "liveness failure",
        "readiness failure",
        "repeated 5xx responses",
        "database connection failure",
        "migration readiness failure",
        "protected route access anomaly",
        "missing observability contract",
    ]:
        assert term in content


def test_p9_rollback_rehearsal_documents_execution_and_database_safety() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Mark the rehearsal target as isolated.",
        "Rehearse switching to the previous known-good image.",
        "Rehearse reapplying previous known-good configuration.",
        "GET /health",
        "GET /runtime/ready",
        "GET /runtime/config",
        "GET /runtime/observability",
        "prefer forward-fix migration when safe",
        "do not run destructive rollback on live production",
        "confirm schema compatibility with selected image",
    ]:
        assert term in content


def test_p9_rollback_rehearsal_documents_verification_stop_evidence_and_exit() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "candidate image identified",
        "previous known-good image identified",
        "rollback decision owner identified",
        "previous known-good image is unknown",
        "previous known-good configuration is unknown",
        "workflow gate bypass is required",
        "candidate image tag or digest",
        "database decision path",
        "Rollback rehearsal is complete when",
        "no guardrail was bypassed",
        "Do not record secrets, connection strings, tokens, or private runtime values.",
    ]:
        assert term in content


def test_p9_rollback_rehearsal_preserves_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "No public production launch.",
        "No destructive production rollback.",
        "No restore over live production traffic.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
        "No workflow gate bypass.",
        "No automatic approval.",
    ]:
        assert term in content
