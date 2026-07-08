from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


REPORT = Path("docs/operations/p25-readiness-report.md")
CHECKLIST = Path("docs/operations/p25-closeout-checklist.md")


def test_p25_closeout_files_reference_parent_issue_and_final_pr() -> None:
    report = REPORT.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")

    for content in [report, checklist]:
        assert "Parent epic: #327" in content
        assert "Final closeout issue: #343" in content
        assert "Final closeout PR: PR_NUMBER_PENDING" in content


def test_p25_closeout_report_records_child_evidence() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for term in [
        "#338",
        "#339",
        "#340",
        "#341",
        "#342",
        "#381",
        "#382",
        "#383",
        "#384",
        "#385",
        "f954d76fa657a9b959a205767618d96050d18017",
        "994ddb2eebce2671d8cacd38e42a509c285c5298",
        "7499a611af7f364354ebf9a9948dae96d93fc19c",
        "e1bd07876572956b0ddb8b9fdf26397375b9fa4c",
        "d16129d2820a4e8e155b323694d43a6c3136adfc",
        "28971412732",
        "28972020891",
        "28972404324",
        "28973069934",
        "28973407002",
    ]:
        assert term in report


def test_p25_closeout_report_documents_packaging_retention_and_handoff() -> None:
    report = REPORT.read_text(encoding="utf-8")
    for term in [
        "YouTube hook and retention scoring rubric",
        "first 1 second thumb-stop criteria",
        "first 3 seconds clarity criteria",
        "first 8 seconds retention-lock criteria",
        "midpoint reset criteria",
        "CTA/comment-trigger criteria",
        "deterministic YouTube title option helper",
        "deterministic first-frame and thumbnail concept helper",
        "deterministic `retention_score.json` report helper",
        "deterministic CTA/comment-trigger helper",
        "package integration paths for title, visual, retention, and CTA fields",
        "`packaging.title_options`",
        "`packaging.first_frame_options`",
        "`packaging.thumbnail_concepts`",
        "`packaging.cta_comment_trigger_options`",
        "`retention.retention_score_path`",
        "P26: rights classification",
        "P27: platform-specific export folders",
        "P28: long-form 16:9 planning",
        "P29: human editorial review",
    ]:
        assert term in report


def test_p25_closeout_checklist_records_files_checks_and_closeout_conditions() -> None:
    checklist = CHECKLIST.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p25-step-01.md",
        "docs/operations/p25-step-02.md",
        "docs/operations/p25-step-03.md",
        "docs/operations/p25-step-04.md",
        "docs/operations/p25-step-05.md",
        "docs/operations/p25-title-options-example.json",
        "docs/operations/p25-visual-concepts-example.json",
        "docs/operations/p25-retention-score-example.json",
        "docs/operations/p25-cta-library-example.json",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p25-closeout-checklist.md",
        "src/title_options.py",
        "src/visual_concepts.py",
        "src/retention_score.py",
        "src/cta_library.py",
        "tests/integration/test_p25_step_01.py",
        "tests/integration/test_p25_step_02.py",
        "tests/integration/test_p25_step_03.py",
        "tests/integration/test_p25_step_04.py",
        "tests/integration/test_p25_step_05.py",
        "tests/integration/test_p25_step_06.py",
        "P1 Acceptance Harness",
        "P1 Foundation Closeout",
        "P1 Ops Storage",
        "#343 is confirmed closed after merge",
        "Parent epic #327 is updated with final PR, merge commit, and exact-head CI evidence",
        "Parent epic #327 is closed as completed",
    ]:
        assert term in checklist


def test_p25_closeout_guardrails_are_preserved() -> None:
    report = REPORT.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")
    for content in [report, checklist]:
        for term in [
            "No misleading clickbait.",
            "No unsupported claims.",
            "No fabricated football facts.",
            "No fake injury framing.",
            "No fake scandal framing.",
            "No automatic title approval.",
            "No automatic visual approval.",
            "No automatic retention approval.",
            "No automatic CTA approval.",
            "No automatic upload.",
            "No automatic publishing.",
            "No automatic monetization approval.",
            "No automatic rights clearance.",
            "No automatic editorial approval.",
            "No YouTube API A/B testing.",
            "No YouTube Analytics ingestion.",
            "No comment scraping.",
            "No comment posting.",
            "No workflow gate bypass.",
            "No implementation without scoped issue and PR.",
            "No merge without exact-head CI.",
        ]:
            assert term in content
