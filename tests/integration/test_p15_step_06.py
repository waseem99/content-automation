from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p15-readiness-report.md")
CHECKLIST = Path("docs/operations/p15-closeout-checklist.md")
EXPECTED_CLOSEOUT_PR = "#221"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p15_closeout_documents_exist() -> None:
    assert REPORT.exists()
    assert CHECKLIST.exists()


def test_p15_closeout_pr_number_is_patched() -> None:
    report = _text(REPORT)
    checklist = _text(CHECKLIST)

    assert EXPECTED_CLOSEOUT_PR != "PR_NUMBER_PENDING"
    assert EXPECTED_CLOSEOUT_PR in report
    assert EXPECTED_CLOSEOUT_PR in checklist
    assert "PR_NUMBER_PENDING" not in report
    assert "PR_NUMBER_PENDING" not in checklist


def test_p15_closeout_references_all_completed_issues_and_prs() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "#209",
        "#210",
        "#211",
        "#212",
        "#213",
        "#214",
        "#215",
        "#216",
        "#217",
        "#218",
        "#219",
        "#220",
        "#221",
        "f933481cd5c14ab8477f14084b55c5cb86f40849",
        "80192eba3ab8d39ab838680fc6e164b11ba0f11b",
        "3186e981df96b5bb0f638fc182e8b45e16c89bbe",
        "d2455fb02833cb31047d9354d3af4414aa76c0a3",
        "925c81384e8acf9533b4033f0b218848875a01cd",
    ]:
        assert term in combined


def test_p15_closeout_references_all_deliverables() -> None:
    report = _text(REPORT)

    for term in [
        "docs/operations/p15-step-01.md",
        "docs/operations/p15-step-02.md",
        "docs/operations/p15-step-03.md",
        "docs/operations/p15-step-04.md",
        "docs/operations/p15-step-05.md",
        "docs/operations/p15-readiness-report.md",
        "docs/operations/p15-closeout-checklist.md",
        "tests/integration/test_p15_step_01.py",
        "tests/integration/test_p15_step_02.py",
        "tests/integration/test_p15_step_03.py",
        "tests/integration/test_p15_step_04.py",
        "tests/integration/test_p15_step_05.py",
        "tests/integration/test_p15_step_06.py",
    ]:
        assert term in report


def test_p15_closeout_preserves_required_guardrails() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "No automatic approval.",
        "No workflow gate bypass.",
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


def test_p15_closeout_documents_final_ci_expectations() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "exact-head CI",
        "patched closeout PR head",
    ]:
        assert term in combined
