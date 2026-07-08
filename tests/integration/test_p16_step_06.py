from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p16-readiness-report.md")
CHECKLIST = Path("docs/operations/p16-closeout-checklist.md")
EXPECTED_CLOSEOUT_PR = "PR_NUMBER_PENDING"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p16_closeout_documents_exist() -> None:
    assert REPORT.exists()
    assert CHECKLIST.exists()


def test_p16_closeout_pr_number_is_patched() -> None:
    report = _text(REPORT)
    checklist = _text(CHECKLIST)

    assert EXPECTED_CLOSEOUT_PR != "PR_NUMBER_PENDING"
    assert EXPECTED_CLOSEOUT_PR in report
    assert EXPECTED_CLOSEOUT_PR in checklist
    assert "PR_NUMBER_PENDING" not in report
    assert "PR_NUMBER_PENDING" not in checklist


def test_p16_closeout_references_all_completed_issues_and_prs() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "#222",
        "#223",
        "#224",
        "#225",
        "#226",
        "#227",
        "#228",
        "#229",
        "#230",
        "#231",
        "#232",
        "#233",
        "b18f4585cf4f2fd72c65a269946722825e6d2bfc",
        "f672ac5b4b1d10ddc2f03cbe0321867ad19cad9a",
        "1907b4aaef2e35462352edd6ebb1367a0fb01390",
        "3064705c7531eddabb6d2f4f80e24598187ed642",
        "0c0c7e445344ab75c4e37b86ec5156c9d92b13d5",
    ]:
        assert term in combined


def test_p16_closeout_references_all_deliverables() -> None:
    report = _text(REPORT)

    for term in [
        "docs/operations/p16-step-01.md",
        "docs/operations/p16-step-02.md",
        "docs/operations/p16-step-03.md",
        "docs/operations/p16-step-04.md",
        "docs/operations/p16-step-05.md",
        "docs/operations/p16-readiness-report.md",
        "docs/operations/p16-closeout-checklist.md",
        "tests/integration/test_p16_step_01.py",
        "tests/integration/test_p16_step_02.py",
        "tests/integration/test_p16_step_03.py",
        "tests/integration/test_p16_step_04.py",
        "tests/integration/test_p16_step_05.py",
        "tests/integration/test_p16_step_06.py",
    ]:
        assert term in report


def test_p16_closeout_preserves_required_guardrails() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "No automatic approval.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
        "No public production launch without explicit decision.",
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


def test_p16_closeout_documents_final_ci_expectations() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "exact-head CI",
        "patched closeout PR head",
    ]:
        assert term in combined
