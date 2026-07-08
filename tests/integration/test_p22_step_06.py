from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p22-readiness-report.md")
CHECKLIST = Path("docs/operations/p22-closeout-checklist.md")
EXPECTED_CLOSEOUT_PR = "PR_NUMBER_PENDING"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p22_closeout_documents_exist() -> None:
    assert REPORT.exists()
    assert CHECKLIST.exists()


def test_p22_closeout_pr_number_is_patched() -> None:
    report = _text(REPORT)
    checklist = _text(CHECKLIST)

    assert EXPECTED_CLOSEOUT_PR != "PR_NUMBER_PENDING"
    assert EXPECTED_CLOSEOUT_PR in report
    assert EXPECTED_CLOSEOUT_PR in checklist
    assert "PR_NUMBER_PENDING" not in report
    assert "PR_NUMBER_PENDING" not in checklist


def test_p22_closeout_references_all_completed_issues_and_prs() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "#300",
        "#301",
        "#302",
        "#303",
        "#304",
        "#305",
        "#306",
        "#307",
        "#308",
        "#309",
        "#310",
        "#311",
        "b03d67091093103e576f09042318ff529b4a978b",
        "f6bff56ba89515d1b3c2e17f29b13d9e30584baf",
        "5331ee67deda7e9ceca7e7c9f67e1b4553f8444c",
        "6cf834a5b80ca4ec673d2829d3d77f74486cfdde",
        "a3a2ff0ffbb6f5f5cabecb3c68a823269220407c",
    ]:
        assert term in combined


def test_p22_closeout_references_all_deliverables() -> None:
    report = _text(REPORT)

    for term in [
        "docs/operations/p22-step-01.md",
        "docs/operations/p22-step-02.md",
        "docs/operations/p22-step-03.md",
        "docs/operations/p22-step-04.md",
        "docs/operations/p22-step-05.md",
        "docs/operations/p22-readiness-report.md",
        "docs/operations/p22-closeout-checklist.md",
        "tests/integration/test_p22_step_01.py",
        "tests/integration/test_p22_step_02.py",
        "tests/integration/test_p22_step_03.py",
        "tests/integration/test_p22_step_04.py",
        "tests/integration/test_p22_step_05.py",
        "tests/integration/test_p22_step_06.py",
    ]:
        assert term in report


def test_p22_closeout_preserves_required_guardrails() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "No automatic approval.",
        "No automatic release.",
        "No automatic deletion.",
        "No automatic access changes.",
        "No automatic export.",
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


def test_p22_closeout_documents_final_ci_expectations() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "exact-head CI",
        "patched closeout PR head",
    ]:
        assert term in combined
