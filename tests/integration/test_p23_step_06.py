from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p23-readiness-report.md")
CHECKLIST = Path("docs/operations/p23-closeout-checklist.md")


def test_p23_closeout_files_reference_parent_issue_and_placeholder() -> None:
    report = REPORT.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")

    for content in [report, checklist]:
        assert "Parent epic: #313" in content
        assert "Final closeout issue: #319" in content
        assert "Final closeout PR: PR_NUMBER_PENDING" in content


def test_p23_closeout_report_records_child_evidence() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for term in [
        "#314",
        "#315",
        "#316",
        "#317",
        "#318",
        "#320",
        "#321",
        "#322",
        "#323",
        "#324",
        "e35cabee559424166baacb4510ffd9e21aec3a1c",
        "ea46bc3792da0da85fc6bce34ad1ae1c89b00476",
        "cdc7506be63b4266eaa77193a8c015054355876c",
        "24c909a9d9f525c5b426411790acdef3551adcec",
        "d6be381578f70bee67bd2be29fe5ce6373a61981",
        "28962343525",
        "28962594666",
        "28962841676",
        "28963101050",
        "28963328255",
    ]:
        assert term in report


def test_p23_closeout_report_documents_repository_public_risk_and_manual_decisions() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for term in [
        "visibility: public",
        "default branch: test",
        "auto-merge: disabled",
        "The repository may still be public.",
        "P23 does not change visibility automatically.",
        "return the repository to private",
        "explicit accepted-risk decision",
        "whether the repository returns to private",
        "whether any public visibility risk is formally accepted",
        "whether required checks are enforced as expected",
        "whether secrets or environments require rotation or protection changes",
        "whether dependency/package registry access is appropriate",
        "whether evidence remains within public/private boundaries",
    ]:
        assert term in report


def test_p23_closeout_checklist_records_required_files_checks_and_closeout_conditions() -> None:
    checklist = CHECKLIST.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p23-step-01.md",
        "docs/operations/p23-step-02.md",
        "docs/operations/p23-step-03.md",
        "docs/operations/p23-step-04.md",
        "docs/operations/p23-step-05.md",
        "docs/operations/p23-readiness-report.md",
        "docs/operations/p23-closeout-checklist.md",
        "tests/integration/test_p23_step_01.py",
        "tests/integration/test_p23_step_02.py",
        "tests/integration/test_p23_step_03.py",
        "tests/integration/test_p23_step_04.py",
        "tests/integration/test_p23_step_05.py",
        "tests/integration/test_p23_step_06.py",
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "#319 is confirmed closed after merge",
        "Parent epic #313 is updated with final PR, merge commit, and exact-head CI evidence",
        "Parent epic #313 is closed as completed",
    ]:
        assert term in checklist


def test_p23_closeout_guardrails_are_preserved() -> None:
    report = REPORT.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")
    for content in [report, checklist]:
        for term in [
            "No automatic approval.",
            "No automatic release.",
            "No automatic repository visibility changes.",
            "No automatic access changes.",
            "No automatic branch protection changes.",
            "No automatic required-check changes.",
            "No automatic secret reading.",
            "No automatic secret printing.",
            "No automatic secret inference.",
            "No automatic secret rotation.",
            "No automatic environment changes.",
            "No automatic dependency install.",
            "No automatic dependency upgrade.",
            "No automatic dependency removal.",
            "No automatic package publishing.",
            "No automatic package export.",
            "No automatic evidence collection.",
            "No automatic evidence export.",
            "No workflow gate bypass.",
            "No public production launch without explicit decision.",
            "No implementation without scoped issue and PR.",
            "No merge without exact-head CI.",
            "No secret values in evidence.",
            "No private runtime values in notes.",
            "No customer data exports.",
            "No external package exports.",
            "No publishing.",
            "No scheduling.",
            "No rendering.",
            "No external export.",
        ]:
            assert term in content
