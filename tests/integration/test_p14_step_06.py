from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p14-readiness-report.md")
CHECKLIST = Path("docs/operations/p14-closeout-checklist.md")


def test_p14_closeout_documents_exist() -> None:
    assert REPORT.exists()
    assert CHECKLIST.exists()


def test_p14_closeout_report_links_all_steps_and_evidence() -> None:
    content = REPORT.read_text(encoding="utf-8")

    assert "PR_NUMBER_PENDING" not in content

    for term in [
        "epic #196",
        "Final closeout issue: #202.",
        "Final closeout PR: #208.",
        "#197",
        "#198",
        "#199",
        "#200",
        "#201",
        "#202",
        "#203",
        "#204",
        "#205",
        "#206",
        "#207",
        "#208",
        "docs/operations/p14-step-01.md",
        "docs/operations/p14-step-02.md",
        "docs/operations/p14-step-03.md",
        "docs/operations/p14-step-04.md",
        "docs/operations/p14-step-05.md",
        "tests/integration/test_p14_step_06.py",
    ]:
        assert term in content


def test_p14_closeout_report_documents_readiness_and_exclusions() -> None:
    content = REPORT.read_text(encoding="utf-8")

    for term in [
        "compliance evidence mapping exists",
        "security review cadence exists",
        "access certification exists",
        "control testing exists",
        "audit package preparation exists",
        "final closeout validation checks",
        "secret values",
        "private runtime values",
        "raw credentials",
        "production tokens",
        "customer data exports",
        "external package exports",
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
    ]:
        assert term in content


def test_p14_closeout_checklist_documents_required_evidence_and_gates() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    assert "PR_NUMBER_PENDING" not in content

    for term in [
        "Final closeout PR: #208.",
        "P14-01 compliance evidence mapping document exists.",
        "P14-02 security review cadence document exists.",
        "P14-03 access certification document exists.",
        "P14-04 control testing document exists.",
        "P14-05 audit package preparation document exists.",
        "P14 readiness report exists.",
        "P14 closeout checklist exists.",
        "P14 final validation test exists.",
        "Child issue #202 closes after final PR merge.",
        "Step #202 merges through PR #208.",
        "P1 Acceptance Harness.",
        "P1 Foundation Closeout.",
        "P1 Ops Storage.",
    ]:
        assert term in content


def test_p14_closeout_checklist_documents_guardrails_and_epic_rule() -> None:
    content = CHECKLIST.read_text(encoding="utf-8")

    for term in [
        "No automatic approval.",
        "No workflow gate bypass.",
        "No public production launch decision is made by P14.",
        "No release is scheduled by P14.",
        "No control closes without evidence.",
        "No access review closes with missing inventory.",
        "No accepted exception exists without owner and expiry date.",
        "No secret values are stored in evidence.",
        "No private runtime values are stored in notes.",
        "No publishing occurs.",
        "No scheduling occurs.",
        "No rendering occurs.",
        "No external export occurs.",
        "final PR #208 is patched with the actual PR number",
        "final exact-head CI passes",
        "issue #202 is confirmed closed",
        "epic #196 is updated with final CI evidence",
    ]:
        assert term in content
