from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p24-step-02.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p24_platform_mapping_references_inputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "docs/operations/p24-step-01.md",
        "README.md",
        "src/cli.py",
        "src/producer.py",
        "src/explainer_producer.py",
        "src/domain/render_status.py",
        "src/assembler/preview_watermark.py",
        ".github/workflows/p1-acceptance-harness.yml",
        "Part of #326. Closes #333 after the PR merges.",
    ]:
        assert term in content


def test_p24_platform_mapping_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This platform mapping matrix is documentation-only.",
        "generate platform exports",
        "create upload descriptions",
        "create title options",
        "create thumbnails",
        "create first-frame options",
        "create hashtags",
        "create pinned comments",
        "render videos",
        "upload to YouTube",
        "upload to TikTok",
        "upload to Instagram",
        "upload to Facebook",
        "post to X/Twitter",
        "approve rights or monetization",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p24_platform_mapping_documents_readiness_states_and_output_groups() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "usable_now_review_only",
        "usable_now_publish_candidate",
        "planned_p25",
        "planned_p26",
        "planned_p27",
        "planned_p28",
        "planned_p29",
        "not_supported_today",
        "Extraction evidence",
        "Short production plan",
        "Explainer production plan",
        "Visual assets",
        "Source evidence",
        "Audio assets",
        "Caption assets",
        "Rendered review assets",
        "Rendered publish candidates",
        "preview_video.mp4",
        "preview_video.mp4.metadata.json",
        "publish_video.mp4",
        "final_video.mp4",
    ]:
        assert term in content


def test_p24_platform_mapping_includes_required_platforms_and_gaps() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "YouTube Shorts",
        "YouTube long-form",
        "TikTok",
        "Instagram Reels",
        "Facebook Reels",
        "X/Twitter",
        "title options",
        "first-frame options",
        "upload description",
        "hashtags",
        "pinned comment",
        "retention score",
        "monetization risk report",
        "rights review",
        "export folder",
        "editorial approval",
        "16:9 render mode",
        "long-form concept model",
        "chapters",
        "thumbnail concepts",
        "source list",
        "music-risk note",
        "cover-frame note",
        "debate prompt",
        "factual caveat",
    ]:
        assert term in content


def test_p24_platform_mapping_documents_platform_specific_constraints() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "vertical 9:16 output",
        "strong first frame",
        "no `preview_video.mp4` publication",
        "true 16:9 render support",
        "6-8 minute or configured long-form duration",
        "chapter structure",
        "native short caption style",
        "platform-safe music review",
        "no assumption that background music is licensed for TikTok",
        "cover-frame guidance",
        "no watermarked cross-platform repost output",
        "monetization/originality note",
        "concise post copy",
        "optional thread for explainers",
        "rights note when video contains broadcast clips or web images",
    ]:
        assert term in content


def test_p24_platform_mapping_documents_downstream_ownership_and_publish_rules() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "P25",
        "P26",
        "P27",
        "P28",
        "P29",
        "YouTube Shorts export pack",
        "TikTok export pack",
        "Instagram Reels export pack",
        "Facebook Reels export pack",
        "X/Twitter export pack",
        "16:9 long-form concept and output contract",
        "series and calendar mapping",
        "human editorial review status",
        "publish-readiness manifest",
        "it is not a preview render",
        "it has a content package reference",
        "platform-specific metadata exists",
        "rights and monetization risk are reviewed",
        "music license requirements are reviewed",
        "human editorial approval is recorded",
        "no hard blocker remains open",
    ]:
        assert term in content


def test_p24_platform_mapping_documents_stop_conditions_guardrails_and_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "`preview_video.mp4` is selected for upload",
        "platform export is marked publish-ready without rights review",
        "platform export is marked publish-ready without human approval",
        "single caption is reused blindly across all platforms",
        "background music is treated as safe for every platform",
        "`image_sources.json` is treated as copyright clearance",
        "broadcast clips are treated as rights-cleared by default",
        "YouTube long-form is claimed supported without 16:9 output",
        "upload readiness is implied before P27",
        "workflow gate bypass is requested",
        "No automatic platform export.",
        "No automatic upload.",
        "No automatic publishing.",
        "No automatic monetization approval.",
        "No automatic rights clearance.",
        "No automatic legal approval.",
        "No automatic music-license approval.",
        "No automatic thumbnail generation.",
        "No automatic title approval.",
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

    assert "tests/integration/test_p24_step_*.py" in harness
