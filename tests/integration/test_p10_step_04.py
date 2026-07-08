from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p10-step-04.md")


def test_p10_monitoring_review_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p10-step-03.md",
        "docs/operations/p9-step-04.md",
        "docs/operations/p10-step-02.md",
        "controlled exposure",
        "Monitoring window",
    ]:
        assert term in content


def test_p10_monitoring_review_documents_dashboard_and_alert_checks() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "service health signal visible",
        "readiness and migration state visible",
        "API request volume visible",
        "API latency visible",
        "workflow action signal visible",
        "operator approval action signal visible",
        "queue item count visible",
        "audit report request signal visible",
        "healthcheck failure route available",
        "readiness failure route available",
        "protected route access anomaly route available",
    ]:
        assert term in content


def test_p10_monitoring_review_documents_cadence_escalation_and_evidence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Review immediately after smoke test completion.",
        "Review before expanding exposure.",
        "Review before declaring rollout stable.",
        "repeated 5xx responses exceed threshold",
        "latency exceeds threshold",
        "queue grows beyond expected threshold",
        "monitoring window",
        "dashboard checks reviewed",
        "alert checks reviewed",
        "exposure expansion recommendation",
    ]:
        assert term in content


def test_p10_monitoring_review_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "dashboard signals are unavailable",
        "alert routing is unavailable",
        "protected route anomaly appears",
        "rollback owner is unavailable",
        "No exposure expansion without monitoring review.",
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
