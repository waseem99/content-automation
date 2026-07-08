from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p10-step-02.md")


def test_p10_deployment_execution_references_required_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p10-step-01.md",
        "docs/operations/p9-step-01.md",
        "docs/operations/p9-step-05.md",
        "approved production exposure decision record exists",
        "latest exact-head CI is green",
        "rollback owner is available",
        "backup availability is confirmed",
    ]:
        assert term in content


def test_p10_deployment_execution_documents_predeploy_and_execution() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Confirm decision state is go or go with documented limitations.",
        "Confirm rollout window is approved.",
        "Confirm previous known-good image is recorded.",
        "Deploy the approved image tag or digest.",
        "Keep exposure private until smoke checks pass.",
        "GET /health",
        "GET /runtime/ready",
        "GET /runtime/config",
        "GET /runtime/observability",
        "protected routes require operator access",
    ]:
        assert term in content


def test_p10_deployment_execution_documents_hold_points_and_verification() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "before applying production configuration",
        "before any public exposure",
        "after health and readiness checks",
        "after protected route verification",
        "Each hold point requires human acknowledgement.",
        "exact image tag or digest deployed",
        "config route excludes secrets",
        "dashboard signals visible",
        "rollback path remains available",
    ]:
        assert term in content


def test_p10_deployment_execution_documents_stop_conditions_and_evidence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "approved decision record is missing",
        "image tag or digest does not match approval",
        "health check fails",
        "readiness check fails",
        "protected routes are not protected",
        "alert route is unavailable",
        "rollback owner is unavailable",
        "decision record reference",
        "hold point acknowledgements",
        "Do not record secrets, tokens, connection strings, raw operator keys, or private runtime values.",
    ]:
        assert term in content


def test_p10_deployment_execution_preserves_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "No deployment without approved decision record.",
        "No public exposure before smoke checks pass.",
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
