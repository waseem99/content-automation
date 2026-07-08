from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p24-readiness-report.md")
CHECKLIST = Path("docs/operations/p24-closeout-checklist.md")


def test_p24_closeout_files_reference_parent_issue_and_final_pr() -> None:
    report = REPORT.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")

    for content in [report, checklist]:
        assert "Parent epic: #326" in content
        assert "Final closeout issue: #337" in content
        assert "Final closeout PR: #380" in content

    assert "The final closeout PR number was patched from `PR_NUMBER_PENDING` to `#380` before merge." in report
    assert "Final closeout files are patched with the actual PR number before merge: #380." in checklist


def test_p24_closeout_report_records_child_evidence() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for term in [
        "#332",
        "#333",
        "#334",
        "#335",
        "#336",
        "#368",
        "#374",
        "#377",
        "#378",
        "#379",
        "7f812cf5242cea866dc87a59afd4a68f6bc7ff5d",
        "9fcc42e42b8367d24a34c123c4832dfc84715f8d",
        "69637df94c15c30215e247e684baef9c3d374056",
        "14b35a8c9126d2cb6806f876943b19ea2e4f988f",
        "141fd8cb12cf72458f9277bf8e4b3ce109c8b1cd",
        "28966480843",
        "28967952454",
        "28969340292",
        "28970319072",
        "28970622048",
    ]:
        assert term in report


def test_p24_closeout_report_documents_readiness_and_downstream_handoff() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for term in [
        "current extraction, Short, and explainer output inventory",
        "platform mapping for YouTube Shorts, YouTube long-form, TikTok, Instagram Reels, Facebook Reels, and X/Twitter",
        "required `content_package.json` top-level fields",
        "Short and explainer example package contracts",
        "deterministic local-file-only package generator helper",
        "pending placeholders for P25 packaging and retention",
        "pending placeholders for P26 rights and monetization",
        "pending placeholders for P27 platform export packs",
        "pending placeholders for P29 editorial review",
        "package creation is not publish approval",
        "P25: YouTube packaging",
        "P26: asset rights classification",
        "P27: platform-specific export folders",
        "P28: long-form 16:9 planning",
        "P29: editorial status model",
    ]:
        assert term in report


def test_p24_closeout_checklist_records_files_checks_and_closeout_conditions() -> None:
    checklist = CHECKLIST.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p24-step-01.md",
        "docs/operations/p24-step-02.md",
        "docs/operations/p24-step-03.md",
        "docs/operations/p24-step-04.md",
        "docs/operations/p24-step-05.md",
        "docs/operations/p24-content-package-short-example.json",
        "docs/operations/p24-content-package-explainer-example.json",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p24-closeout-checklist.md",
        "src/content_package.py",
        "tests/integration/test_p24_step_01.py",
        "tests/integration/test_p24_step_02.py",
        "tests/integration/test_p24_step_03.py",
        "tests/integration/test_p24_step_04.py",
        "tests/integration/test_p24_step_05.py",
        "tests/integration/test_p24_step_06.py",
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "#337 is confirmed closed after merge",
        "Parent epic #326 is updated with final PR, merge commit, and exact-head CI evidence",
        "Parent epic #326 is closed as completed",
    ]:
        assert term in checklist


def test_p24_closeout_guardrails_are_preserved() -> None:
    report = REPORT.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")
    for content in [report, checklist]:
        for term in [
            "No automatic approval.",
            "No automatic release.",
            "No automatic rendering.",
            "No automatic publishing.",
            "No automatic upload.",
            "No automatic rights clearance.",
            "No automatic monetization approval.",
            "No automatic legal approval.",
            "No automatic platform export.",
            "No automatic editorial approval.",
            "No workflow gate bypass.",
            "No implementation without scoped issue and PR.",
            "No merge without exact-head CI.",
            "No secret values in evidence.",
            "No private runtime values in notes.",
            "No customer data exports.",
            "No external package exports.",
        ]:
            assert term in content
