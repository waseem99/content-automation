from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p14-step-04.md")


def test_p14_control_testing_references_previous_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p14-step-01.md",
        "docs/operations/p14-step-02.md",
        "docs/operations/p14-step-03.md",
        "docs/operations/p13-readiness-report.md",
    ]:
        assert term in content


def test_p14_control_testing_documents_inputs_and_fields() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "compliance evidence map",
        "access certification evidence",
        "security review evidence",
        "operational runbook evidence",
        "incident and action tracking evidence",
        "backup and restore evidence",
        "failover readiness evidence",
        "capacity planning evidence",
        "resilience drill evidence",
        "CI validation evidence",
        "open exception evidence",
        "control identifier",
        "control objective",
        "test procedure",
        "evidence source",
        "result state",
        "target review date",
        "evidence archive entry",
    ]:
        assert term in content


def test_p14_control_testing_documents_owners_and_states() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "control owner",
        "test owner",
        "reviewer",
        "evidence owner",
        "action owner",
        "exception owner",
        "audit package owner",
        "primary owner and backup owner",
        "ownerless failures",
        "pass with current evidence",
        "pass with observation",
        "corrective action required",
        "evidence refresh required",
        "retest required",
        "exception accepted with owner and expiry date",
        "blocked because evidence is missing",
    ]:
        assert term in content


def test_p14_control_testing_documents_action_tracking_and_cadence() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "Failed or incomplete control tests must record",
        "finding summary",
        "evidence required for closure",
        "current action status",
        "escalation owner when overdue",
        "final reviewer decision",
        "control testing quarterly",
        "high-risk control testing monthly",
        "access control testing quarterly",
        "security control testing monthly",
        "resilience control testing quarterly",
        "control evidence review before audit package closeout",
        "retest after corrective action completion",
    ]:
        assert term in content


def test_p14_control_testing_documents_closure_stops_and_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "test procedure is documented",
        "failed or incomplete result has an action owner",
        "accepted exception has owner and expiry date",
        "control objective is missing",
        "test procedure is missing",
        "failed or incomplete result lacks action owner",
        "accepted exception lacks expiry date",
        "retest requirement is missing after corrective action",
        "evidence contains secret values",
        "notes contain private runtime values",
        "workflow gate bypass is requested",
        "No control closure without evidence.",
        "No control testing closure without tester and reviewer.",
        "No failed or incomplete control test without action owner.",
        "No accepted exception without owner and expiry date.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No automatic approval.",
        "No workflow gate bypass.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in content
