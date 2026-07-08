from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p13-step-04.md")


def test_p13_capacity_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p12-step-03.md",
        "docs/operations/p13-step-03.md",
        "docs/operations/p13-step-01.md",
    ]:
        assert term in content


def test_p13_capacity_documents_signals_thresholds_and_owners() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "request volume",
        "error rate",
        "response latency",
        "worker queue depth",
        "database connection pressure",
        "workflow duration",
        "current baseline",
        "warning threshold",
        "critical threshold",
        "corrective action trigger",
        "capacity planning owner",
        "primary owner and backup owner",
    ]:
        assert term in content


def test_p13_capacity_documents_forecast_scaling_and_evidence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "monthly capacity review",
        "quarterly forecast update",
        "review before significant exposure expansion",
        "add capacity",
        "optimize workload",
        "request architecture review",
        "accept documented risk with owner and expiry date",
        "forecast assumption",
        "scaling decision",
        "evidence archive entry",
    ]:
        assert term in content


def test_p13_capacity_documents_stop_conditions_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "capacity owner is missing",
        "critical signal lacks threshold",
        "critical threshold breach lacks action owner",
        "forecast assumption is missing",
        "accepted risk lacks expiry date",
        "No capacity review closure without evidence.",
        "No critical threshold breach without action owner.",
        "No accepted capacity risk without expiry date.",
        "No ownerless capacity signal.",
        "No automatic approval.",
        "No workflow gate bypass.",
    ]:
        assert term in content
