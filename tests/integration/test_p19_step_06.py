from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p19-readiness-report.md")
CHECKLIST = Path("docs/operations/p19-closeout-checklist.md")
EXPECTED_CLOSEOUT_PR = "PR_NUMBER_PENDING"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p19_closeout_documents_exist() -> None:
    assert REPORT.exists()
    assert CHECKLIST.exists()


def test_p19_closeout_pr_number_is_patched() -> None:
    report = _text(REPORT)
    checklist = _text(CHECKLIST)

    assert EXPECTED_CLOSEOUT_PR != "PR_NUMBER_PENDING"
    assert EXPECTED_CLOSEOUT_PR in report
    assert EXPECTED_CLOSEOUT_PR in checklist
    assert "PR_NUMBER_PENDING" not in report
    assert "PR_NUMBER_PENDING" not in checklist


def test_p19_closeout_references_all_completed_issues_and_prs() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "#261",
        "#262",
        "#263",
        "#264",
        "#265",
        "#266",
        "#267",
        "#268",
        "#269",
        "#270",
        "#271",
        "#272",
        "0bb0e70a6e29c9a06b2b9f6716ac7934e8a76a30",
        "084b762721ab1eb1eb7356de01f7797d0a8f1ac2",
        "0eb944e88880f5ddf7a3077e24974658fd55cf42",
        "e4e1cc1a6839df31dc274ff5d18209a16ce81496",
        "e0be79839693d1fcf631673813f389700a5314f3",
    ]:
        assert term in combined


def test_p19_closeout_references_all_deliverables() -> None:
    report = _text(REPORT)

    for term in [
        "docs/operations/p19-step-01.md",
        "docs/operations/p19-step-02.md",
        "docs/operations/p19-step-03.md",
        "docs/operations/p19-step-04.md",
        "docs/operations/p19-step-05.md",
        "docs/operations/p19-readiness-report.md",
        "docs/operations/p19-closeout-checklist.md",
        "tests/integration/test_p19_step_01.py",
        "tests/integration/test_p19_step_02.py",
        "tests/integration/test_p19_step_03.py",
        "tests/integration/test_p19_step_04.py",
        "tests/integration/test_p19_step_05.py",
        "tests/integration/test_p19_step_06.py",
    ]:
        assert term in report


def test_p19_closeout_preserves_required_guardrails() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "No automatic approval.",
        "No automatic release.",
        "No workflow gate bypass.",
        "No public production launch without explicit decision.",
        "No release without calendar entry.",
        "No release during blackout window.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No permanent exceptions.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No customer data exports.",
        "No external package exports.",
        "No publishing.",
        "No scheduling.",
        "No rendering.",
        "No external export.",
    ]:
        assert term in combined


def test_p19_closeout_documents_final_ci_expectations() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "exact-head CI",
        "patched closeout PR head",
    ]:
        assert term in combined
