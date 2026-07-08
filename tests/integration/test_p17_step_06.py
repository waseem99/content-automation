from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p17-readiness-report.md")
CHECKLIST = Path("docs/operations/p17-closeout-checklist.md")
EXPECTED_CLOSEOUT_PR = "#247"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p17_closeout_documents_exist() -> None:
    assert REPORT.exists()
    assert CHECKLIST.exists()


def test_p17_closeout_pr_number_is_patched() -> None:
    report = _text(REPORT)
    checklist = _text(CHECKLIST)

    assert EXPECTED_CLOSEOUT_PR != "PR_NUMBER_PENDING"
    assert EXPECTED_CLOSEOUT_PR in report
    assert EXPECTED_CLOSEOUT_PR in checklist
    assert "PR_NUMBER_PENDING" not in report
    assert "PR_NUMBER_PENDING" not in checklist


def test_p17_closeout_references_all_completed_issues_and_prs() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "#235",
        "#236",
        "#237",
        "#238",
        "#239",
        "#240",
        "#241",
        "#242",
        "#243",
        "#244",
        "#245",
        "#246",
        "#247",
        "dc82d3ed441a93e7a316d167e00bbfa22f37a193",
        "375592aef94ca19680ac46529d489f4970ec50bd",
        "1428adddf514a7da8dce0251e49669d467bec582",
        "d372ed492ac2c454fff56b688bb8ce7adc141b8e",
        "6227516905863daf6565eb8c36cac93d5d58089a",
    ]:
        assert term in combined


def test_p17_closeout_references_all_deliverables() -> None:
    report = _text(REPORT)

    for term in [
        "docs/operations/p17-step-01.md",
        "docs/operations/p17-step-02.md",
        "docs/operations/p17-step-03.md",
        "docs/operations/p17-step-04.md",
        "docs/operations/p17-step-05.md",
        "docs/operations/p17-readiness-report.md",
        "docs/operations/p17-closeout-checklist.md",
        "tests/integration/test_p17_step_01.py",
        "tests/integration/test_p17_step_02.py",
        "tests/integration/test_p17_step_03.py",
        "tests/integration/test_p17_step_04.py",
        "tests/integration/test_p17_step_05.py",
        "tests/integration/test_p17_step_06.py",
    ]:
        assert term in report


def test_p17_closeout_preserves_required_guardrails() -> None:
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


def test_p17_closeout_documents_final_ci_expectations() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "exact-head CI",
        "patched closeout head",
    ]:
        assert term in combined
