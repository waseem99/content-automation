from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p14-step-02.md")


def test_p14_security_review_references_p14_and_p13_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "docs/operations/p14-step-01.md",
        "docs/operations/p13-readiness-report.md",
        "docs/operations/p13-closeout-checklist.md",
    ]:
        assert term in content


def test_p14_security_review_documents_cadence_and_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "security evidence review monthly",
        "dependency and package review monthly",
        "access-sensitive surface review quarterly",
        "incident action review monthly",
        "security review after any material production change",
        "pre-audit security review before audit package closeout",
        "compliance evidence map status",
        "open security findings",
        "dependency update evidence",
        "runtime configuration change evidence",
        "access review evidence",
        "dashboard and alert routing evidence",
        "accepted exceptions and expiry dates",
    ]:
        assert term in content


def test_p14_security_review_documents_owners_and_outputs() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "security review owner",
        "evidence owner",
        "control owner",
        "dependency owner",
        "runtime configuration owner",
        "access review owner",
        "alert routing owner",
        "action owner",
        "exception owner",
        "primary owner and backup owner",
        "ownerless findings",
        "review date",
        "reviewer names or roles",
        "reviewed evidence list",
        "decision summary",
        "open finding list",
        "action tracker updates",
        "evidence archive entry",
    ]:
        assert term in content


def test_p14_security_review_documents_escalation_decisions_and_stops() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "high-severity finding has no action owner",
        "secret value appears in evidence",
        "private runtime value appears in notes",
        "accepted exception lacks expiry date",
        "access evidence is incomplete",
        "workflow gate bypass is requested",
        "security posture accepted with current evidence",
        "corrective action required",
        "evidence refresh required",
        "alert routing update required",
        "dependency update required",
        "audit package update required",
        "reviewed evidence list is missing",
        "dependency update evidence is missing",
    ]:
        assert term in content


def test_p14_security_review_documents_guardrails() -> None:
    content = DOC.read_text(encoding="utf-8")

    for term in [
        "No security review closure without reviewed evidence.",
        "No ownerless high-severity finding.",
        "No accepted exception without owner and expiry date.",
        "No access review closure with missing inventory.",
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
