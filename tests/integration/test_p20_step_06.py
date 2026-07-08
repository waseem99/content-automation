from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p20-readiness-report.md")
CHECKLIST = Path("docs/operations/p20-closeout-checklist.md")
EXPECTED_CLOSEOUT_PR = "#286"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_p20_closeout_documents_exist() -> None:
    assert REPORT.exists()
    assert CHECKLIST.exists()


def test_p20_closeout_pr_number_is_patched() -> None:
    report = _text(REPORT)
    checklist = _text(CHECKLIST)

    assert EXPECTED_CLOSEOUT_PR != "PR_NUMBER_PENDING"
    assert EXPECTED_CLOSEOUT_PR in report
    assert EXPECTED_CLOSEOUT_PR in checklist
    assert "PR_NUMBER_PENDING" not in report
    assert "PR_NUMBER_PENDING" not in checklist


def test_p20_closeout_references_all_completed_issues_and_prs() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "#274",
        "#275",
        "#276",
        "#277",
        "#278",
        "#279",
        "#280",
        "#281",
        "#282",
        "#283",
        "#284",
        "#285",
        "#286",
        "9d590033c81e885163c840c89d7a72ca09293a20",
        "7f143d835373ce3315d61d9877dad1e3de8b385e",
        "9e4c7e1c21dfe07335d948a8c52b8139421541f7",
        "72959f392c277483061cb3c05cd85e33a4c5356e",
        "a2e80877dc73d24e49c218707d7279caad644615",
    ]:
        assert term in combined


def test_p20_closeout_references_all_deliverables() -> None:
    report = _text(REPORT)

    for term in [
        "docs/operations/p20-step-01.md",
        "docs/operations/p20-step-02.md",
        "docs/operations/p20-step-03.md",
        "docs/operations/p20-step-04.md",
        "docs/operations/p20-step-05.md",
        "docs/operations/p20-readiness-report.md",
        "docs/operations/p20-closeout-checklist.md",
        "tests/integration/test_p20_step_01.py",
        "tests/integration/test_p20_step_02.py",
        "tests/integration/test_p20_step_03.py",
        "tests/integration/test_p20_step_04.py",
        "tests/integration/test_p20_step_05.py",
        "tests/integration/test_p20_step_06.py",
    ]:
        assert term in report


def test_p20_closeout_preserves_required_guardrails() -> None:
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


def test_p20_closeout_documents_final_ci_expectations() -> None:
    combined = _text(REPORT) + "\n" + _text(CHECKLIST)

    for term in [
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "exact-head CI",
        "patched closeout PR head",
    ]:
        assert term in combined
