from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p21-readiness-report.md")
CHECKLIST = Path("docs/operations/p21-closeout-checklist.md")
EXPECTED_CLOSEOUT_PR = "#299"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p21_closeout_documents_exist() -> None:
    assert REPORT.exists()
    assert CHECKLIST.exists()


def test_p21_closeout_pr_number_is_patched() -> None:
    report = _text(REPORT)
    checklist = _text(CHECKLIST)

    assert EXPECTED_CLOSEOUT_PR != "PR_NUMBER_PENDING"
    assert EXPECTED_CLOSEOUT_PR in report
    assert EXPECTED_CLOSEOUT_PR in checklist
    assert "PR_NUMBER_PENDING" not in report
    assert "PR_NUMBER_PENDING" not in checklist


def test_p21_closeout_references_all_completed_issues_and_prs() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "#287",
        "#288",
        "#289",
        "#290",
        "#291",
        "#292",
        "#293",
        "#294",
        "#295",
        "#296",
        "#297",
        "#298",
        "#299",
        "a279031c9b170380005712cc5116c95ac4240cbe",
        "cac7997fff5879f8d97071479a58ee0e4a874094",
        "b72c7d4769d4ce614471b070310c778e6d52abfe",
        "892e84568af9d23f8371ac0233c49053955cf40e",
        "110b21be93778a20af32df36ac765d8536036cb7",
    ]:
        assert term in combined


def test_p21_closeout_references_all_deliverables() -> None:
    report = _text(REPORT)

    for term in [
        "docs/operations/p21-step-01.md",
        "docs/operations/p21-step-02.md",
        "docs/operations/p21-step-03.md",
        "docs/operations/p21-step-04.md",
        "docs/operations/p21-step-05.md",
        "docs/operations/p21-readiness-report.md",
        "docs/operations/p21-closeout-checklist.md",
        "tests/integration/test_p21_step_01.py",
        "tests/integration/test_p21_step_02.py",
        "tests/integration/test_p21_step_03.py",
        "tests/integration/test_p21_step_04.py",
        "tests/integration/test_p21_step_05.py",
        "tests/integration/test_p21_step_06.py",
    ]:
        assert term in report


def test_p21_closeout_preserves_required_guardrails() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "No automatic approval.",
        "No automatic release.",
        "No automatic escalation.",
        "No automatic operator action.",
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


def test_p21_closeout_documents_final_ci_expectations() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "exact-head CI",
        "patched closeout PR head",
    ]:
        assert term in combined
