from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p26-readiness-report.md")
CHECKLIST = Path("docs/operations/p26-closeout-checklist.md")


def test_p26_closeout_files_reference_parent_issue_and_final_pr() -> None:
    report = REPORT.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")

    for content in [report, checklist]:
        assert "Parent epic: #328" in content
        assert "Final closeout issue: #349" in content
        assert "Final closeout PR: #396" in content

    assert "The final closeout PR number was patched from `PR_NUMBER_PENDING` to `#396` before merge." in report
    assert "Final closeout files are patched with the actual PR number before merge: #396." in checklist


def test_p26_closeout_report_records_child_evidence() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for term in [
        "#344",
        "#345",
        "#346",
        "#347",
        "#348",
        "#387",
        "#388",
        "#393",
        "#394",
        "#395",
        "20c8d1d467eb4618934638908bb82713eb0e8a68",
        "51d20524005762d923f3e0c0e6a16a0c9d1867fb",
        "b5dbcceabf263aee9efb541bc23d34a07b051d77",
        "f82684d44b9d8bcab3fbe14ac98670f98997d242",
        "d2efd2926f24ff216f37a72dd56ccfb7d0d30cf1",
        "28974359525",
        "28974727927",
        "28993583307",
        "28993824715",
        "28994004507",
    ]:
        assert term in report


def test_p26_closeout_report_documents_readiness_and_residual_risk() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for term in [
        "asset rights classification model",
        "default risk levels for broadcast clips, extracted clips, web images, AI images, music, logos, scripts, stats, titles, CTAs, and retention reports",
        "`monetization_risk_report.json` schema",
        "low, medium, and high monetization-risk example reports",
        "source attribution and license tracking requirements",
        "example attribution records for images, stats, music, extracted clips, AI visuals, and title options",
        "originality layer requirements for Shorts and explainers",
        "weak and stronger originality examples",
        "publish-block rules for unresolved rights, music, image, source, originality, and editorial risks",
        "blocked, review-required, and export-candidate-after-review publish decision examples",
        "P26 does not make any content publish-ready.",
        "`publish_allowed` defaults to `false`",
        "high-risk packages remain blocked",
        "low-risk reports are not publish approvals",
        "source URLs are not license approvals",
        "`image_sources.json` is source evidence only",
        "Residual risks requiring human review",
        "legal interpretation of fair use, copyright, or platform policy",
        "actual platform monetization decisions",
        "Content ID behavior",
        "music-license scope by platform",
        "P29: editorial governance",
    ]:
        assert term in report


def test_p26_closeout_checklist_records_files_checks_and_conditions() -> None:
    checklist = CHECKLIST.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p26-step-01.md",
        "docs/operations/p26-step-02.md",
        "docs/operations/p26-step-03.md",
        "docs/operations/p26-step-04.md",
        "docs/operations/p26-step-05.md",
        "docs/operations/p26-risk-report-low-example.json",
        "docs/operations/p26-risk-report-medium-example.json",
        "docs/operations/p26-risk-report-high-example.json",
        "docs/operations/p26-source-attribution-example.json",
        "docs/operations/p26-originality-layer-example.json",
        "docs/operations/p26-publish-block-examples.json",
        "docs/operations/p26-readiness-report.md",
        "docs/operations/p26-closeout-checklist.md",
        "tests/integration/test_p26_step_01.py",
        "tests/integration/test_p26_step_02.py",
        "tests/integration/test_p26_step_03.py",
        "tests/integration/test_p26_step_04.py",
        "tests/integration/test_p26_step_05.py",
        "tests/integration/test_p26_step_06.py",
        "#344 closed through PR #387.",
        "#345 closed through PR #388.",
        "#346 closed through PR #393.",
        "#347 closed through PR #394.",
        "#348 closed through PR #395.",
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "#349 is confirmed closed after merge",
        "Parent epic #328 is updated with final PR, merge commit, and exact-head CI evidence",
        "Parent epic #328 is closed as completed",
    ]:
        assert term in checklist


def test_p26_closeout_guardrails_are_preserved() -> None:
    report = REPORT.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")
    for content in [report, checklist]:
        for term in [
            "No automated legal clearance.",
            "No copyright claim prediction.",
            "No Content ID prediction.",
            "No automatic license verification.",
            "No automatic rights clearance.",
            "No automatic monetization approval.",
            "No automatic publishing approval.",
            "No automatic upload.",
            "No automatic publishing.",
            "No platform API enforcement.",
            "No direct platform enforcement.",
            "No auto-removing risky content.",
            "No automatic attribution approval.",
            "No automatic originality approval.",
            "No automatic reused-content clearance.",
            "No workflow gate bypass.",
            "No implementation without scoped issue and PR.",
            "No merge without exact-head CI.",
        ]:
            assert term in content
