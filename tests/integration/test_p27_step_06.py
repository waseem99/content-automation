from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

REPORT = Path("docs/operations/p27-closeout-report.md")
CHECKLIST = Path("docs/operations/p27-closeout-checklist.json")

P27_ARTIFACTS = [
    "docs/operations/p27-step-01.md",
    "docs/operations/p27-export-directory-example.json",
    "tests/integration/test_p27_step_01.py",
    "src/youtube_shorts_export.py",
    "docs/operations/p27-step-02.md",
    "docs/operations/p27-youtube-shorts-export-example.json",
    "tests/integration/test_p27_step_02.py",
    "src/short_form_exports.py",
    "docs/operations/p27-step-03.md",
    "docs/operations/p27-short-form-export-example.json",
    "tests/integration/test_p27_step_03.py",
    "src/x_twitter_export.py",
    "docs/operations/p27-step-04.md",
    "docs/operations/p27-x-twitter-export-example.json",
    "tests/integration/test_p27_step_04.py",
    "src/export_readiness.py",
    "docs/operations/p27-step-05.md",
    "docs/operations/p27-cross-platform-readiness-example.json",
    "tests/integration/test_p27_step_05.py",
    "docs/operations/p27-closeout-report.md",
    "docs/operations/p27-closeout-checklist.json",
    "tests/integration/test_p27_step_06.py",
]

PLATFORMS = {
    "youtube_shorts": "exports/youtube_shorts/",
    "tiktok": "exports/tiktok/",
    "instagram_reels": "exports/instagram_reels/",
    "facebook_reels": "exports/facebook_reels/",
    "x_twitter": "exports/x_twitter/",
}


def test_p27_closeout_report_references_scope_and_child_tasks() -> None:
    content = REPORT.read_text(encoding="utf-8")
    for term in [
        "Part of #329. Closes #355 after the PR merges.",
        "#350",
        "#351",
        "#352",
        "#353",
        "#354",
        "#355",
        "P27-01 — Define platform export directory contract",
        "P27-02 — Generate YouTube Shorts export pack",
        "P27-03 — Generate TikTok, Instagram Reels, and Facebook Reels export packs",
        "P27-04 — Generate X/Twitter caption and thread export pack",
        "P27-05 — Validate cross-platform export readiness",
        "P27-06 — P27 platform export closeout",
    ]:
        assert term in content


def test_p27_closeout_report_confirms_platform_exports_and_validation() -> None:
    content = REPORT.read_text(encoding="utf-8")
    for platform, directory in PLATFORMS.items():
        assert platform in content
        assert directory in content

    for term in [
        "publish_allowed: false",
        "review_required: true",
        "is_publish_ready: false",
        "P26 risk state remains visible",
        "blocking reasons and required actions carry through to review status",
        "blocked content does not appear as `publish_ready`",
        "P29 editorial approval remains required",
        "manual review remains separate from publishing approval",
    ]:
        assert term in content


def test_p27_closeout_report_documents_remaining_gaps_and_guardrails() -> None:
    content = REPORT.read_text(encoding="utf-8")
    for term in [
        "YouTube API upload",
        "TikTok API upload",
        "Meta/Instagram/Facebook upload APIs",
        "X API posting",
        "platform credential storage",
        "live platform post previews",
        "platform analytics ingestion",
        "engagement/reply scraping",
        "automated music licensing",
        "automatic rights clearance",
        "automatic monetization approval",
        "automatic editorial approval",
        "treat export readiness as publish approval",
        "default `publish_allowed` to `true`",
        "bypass P26 publish-block rules",
        "bypass P29 editorial approval",
        "commit external rendered video assets",
        "commit secrets",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p27_closeout_checklist_schema_and_child_task_statuses() -> None:
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))

    assert checklist["schema_version"] == "p27.closeout_checklist.v1"
    assert checklist["parent_epic"] == 329
    assert checklist["closeout_issue"] == 355
    assert checklist["publish_allowed"] is False
    assert checklist["review_required"] is True
    assert checklist["p27_complete_after_issue_355_merge"] is True

    child_tasks = checklist["child_tasks"]
    assert [task["issue"] for task in child_tasks] == [350, 351, 352, 353, 354, 355]
    assert [task["step"] for task in child_tasks] == ["P27-01", "P27-02", "P27-03", "P27-04", "P27-05", "P27-06"]

    for task in child_tasks[:-1]:
        assert task["status"] == "complete"
        assert task["required_artifacts"]

    assert child_tasks[-1]["status"] == "complete_after_merge"


def test_p27_closeout_checklist_artifacts_exist() -> None:
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    checklist_artifacts = {
        artifact
        for task in checklist["child_tasks"]
        for artifact in task["required_artifacts"]
    }

    assert checklist_artifacts == set(P27_ARTIFACTS)

    for artifact in checklist_artifacts:
        assert Path(artifact).exists(), artifact


def test_p27_closeout_checklist_platforms_validation_and_gaps() -> None:
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))

    platform_exports = checklist["platform_exports"]
    assert {platform["platform"]: platform["directory"] for platform in platform_exports} == PLATFORMS
    assert all(platform["status"] == "review_only_export_pack_defined" for platform in platform_exports)

    validation = checklist["validation_summary"]
    assert validation["cross_platform_validator"] == "src/export_readiness.py"
    assert validation["readiness_example"] == "docs/operations/p27-cross-platform-readiness-example.json"
    assert validation["is_ready_for_manual_review"] is True
    assert validation["is_publish_ready"] is False
    assert validation["blocked_content_must_not_be_publish_ready"] is True
    assert validation["p26_risk_state_visible"] is True
    assert validation["p29_editorial_required"] is True

    for gap in [
        "YouTube API upload",
        "TikTok API upload",
        "Meta/Instagram/Facebook upload APIs",
        "X API posting",
        "platform analytics ingestion",
        "automated music licensing",
    ]:
        assert gap in checklist["remaining_gaps"]


def test_p27_closeout_guardrails_preserved() -> None:
    checklist = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    guardrails = checklist["guardrails"]

    for guardrail in [
        "No platform upload in P27.",
        "No platform API integration in P27.",
        "No platform credentials in P27.",
        "No external video asset commits.",
        "No secret values.",
        "No automatic publish approval.",
        "No automatic rights clearance.",
        "No automatic monetization approval.",
        "No automatic editorial approval.",
        "No bypass of P26 publish-block rules.",
        "No bypass of P29 editorial governance.",
        "No workflow gate bypass.",
        "No merge without exact-head CI.",
    ]:
        assert guardrail in guardrails
