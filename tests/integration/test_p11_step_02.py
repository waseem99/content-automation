from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p11-step-02.md")


def test_p11_alert_tuning_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p11-step-01.md",
        "docs/operations/p10-step-04.md",
        "docs/operations/p10-step-05.md",
    ]:
        assert term in content


def test_p11_alert_tuning_documents_inventory_and_threshold_review() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "healthcheck failure",
        "readiness failure",
        "repeated 5xx responses",
        "database connection failure",
        "protected route access anomaly",
        "queue growth",
        "workflow failure spike",
        "current threshold",
        "primary owner",
        "backup owner",
        "false positive count",
        "missed signal count",
        "proposed threshold change",
    ]:
        assert term in content


def test_p11_alert_tuning_documents_noisy_and_missed_signal_review() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "A signal is noisy when it triggers without required action.",
        "proposed suppression rule",
        "risk of suppression",
        "A missed signal exists when expected alerting did not occur.",
        "expected trigger",
        "observed symptom",
        "corrective action",
        "validation method",
    ]:
        assert term in content


def test_p11_alert_tuning_documents_outputs_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "threshold changes",
        "route changes",
        "owner changes",
        "critical alert route is unavailable",
        "readiness or health alerts are disabled",
        "threshold change would hide critical failures",
        "No alert disablement without owner approval.",
        "No threshold change that hides critical failures.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No secret values in evidence.",
    ]:
        assert term in content
