from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p18-readiness-report.md")
CHECKLIST = Path("docs/operations/p18-closeout-checklist.md")
EXPECTED_CLOSEOUT_PR = "PR_NUMBER_PENDING"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p18_closeout_documents_exist() -> None:
    assert REPORT.exists()
    assert CHECKLIST.exists()


def test_p18_closeout_pr_number_is_patched() -> None:
    report = _text(REPORT)
    checklist = _text(CHECKLIST)

    assert EXPECTED_CLOSEOUT_PR != "PR_NUMBER_PENDING"
    assert EXPECTED_CLOSEOUT_PR in report
    assert EXPECTED_CLOSEOUT_PR in checklist
    assert "PR_NUMBER_PENDING" not in report
    assert "PR_NUMBER_PENDING" not in checklist


def test_p18_closeout_references_all_completed_issues_and_prs() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "#248",
        "#249",
        "#250",
        "#251",
        "#252",
        "#253",
        "#254",
        "#255",
        "#256",
        "#257",
        "#258",
        "#259",
        "b16f70d3d5218b76ca3e11a29317510852a32e07",
        "c9f151dfc7a4cdccfc5837a563468784f727167f",
        "c81f771a6fa13235406f90015a37631e32df1dc2",
        "872d31508a9a1666cddbe2dd1448c65205c33aa2",
        "2ab9708c3a7803ab8604683f981b9ec48dca0f54",
    ]:
        assert term in combined


def test_p18_closeout_references_all_deliverables() -> None:
    report = _text(REPORT)

    for term in [
        "docs/operations/p18-step-01.md",
        "docs/operations/p18-step-02.md",
        "docs/operations/p18-step-03.md",
        "docs/operations/p18-step-04.md",
        "docs/operations/p18-step-05.md",
        "docs/operations/p18-readiness-report.md",
        "docs/operations/p18-closeout-checklist.md",
        "tests/integration/test_p18_step_01.py",
        "tests/integration/test_p18_step_02.py",
        "tests/integration/test_p18_step_03.py",
        "tests/integration/test_p18_step_04.py",
        "tests/integration/test_p18_step_05.py",
        "tests/integration/test_p18_step_06.py",
    ]:
        assert term in report


def test_p18_closeout_preserves_required_guardrails() -> None:
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


def test_p18_closeout_documents_final_ci_expectations() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "exact-head CI",
        "patched closeout PR head",
    ]:
        assert term in combined
