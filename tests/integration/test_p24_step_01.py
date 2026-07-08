from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p24-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p24_output_inventory_references_current_pipeline_sources() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "README.md",
        "src/cli.py",
        "src/producer.py",
        "src/explainer_producer.py",
        "src/extractor/clip_pool.py",
        "src/generator/script_generator.py",
        "src/generator/explainer_script_generator.py",
        "src/generator/image_generator.py",
        "src/generator/visual_generator.py",
        "src/assembler/mode_assembler.py",
        "src/assembler/video_assembler.py",
        "src/assembler/explainer_assembler.py",
        "src/assembler/preview_watermark.py",
        "src/domain/render_status.py",
        "src/production_checkpoint.py",
        ".github/workflows/p1-acceptance-harness.yml",
        "Part of #326. Closes #332 after the PR merges.",
    ]:
        assert term in content


def test_p24_output_inventory_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "This current content output inventory is documentation-only.",
        "extract match clips",
        "generate scripts",
        "fetch web images",
        "generate AI images",
        "generate voiceovers",
        "assemble videos",
        "render previews",
        "render publish videos",
        "upload to any platform",
        "publish to YouTube",
        "publish to TikTok",
        "publish to Instagram",
        "publish to Facebook",
        "publish to X/Twitter",
        "approve monetization readiness",
        "clear rights or copyright risk",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p24_output_inventory_documents_commands_and_extraction_outputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "`extract`",
        "`manual-cut`",
        "`extract-batch`",
        "`produce`",
        "`produce-explainer`",
        "`list-voices`",
        "data/output/{video_name}_{timestamp}/",
        "data/campaigns/{campaign}/clip_pool/",
        "analysis_audio.wav",
        "clip_*.mp4",
        "manifest.json",
        "concept.yaml",
        "data/campaigns/{campaign}/extractions/",
        "data/campaigns/{campaign}/clip_pool/*.mp4",
        "clip pool `manifest.json`",
        "source video, topic, timestamps, scores, labels, and source text",
    ]:
        assert term in content


def test_p24_output_inventory_documents_shorts_and_explainer_outputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "match_context.txt",
        "production_plan.json",
        "image_intro.png",
        "image_01.png",
        "image_02.png",
        "image_03.png",
        "image_sources.json",
        "narration_*.mp3",
        "subtitles.srt",
        "preview_video.mp4",
        "preview_video.mp4.metadata.json",
        "publish_video.mp4",
        "explainer_plan.json",
        "beat_{section}_{index}.png",
        "beat_comparison_collage.png",
        "checkpoint.json",
        "final_video.mp4",
    ]:
        assert term in content


def test_p24_output_inventory_documents_classifications_and_mismatch() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Production source assets",
        "Intermediate analysis assets",
        "Production plans",
        "Visual assets",
        "Audio assets",
        "Caption assets",
        "Source evidence",
        "Rendered review assets",
        "Rendered publish candidates",
        "README and code mismatch",
        "README currently documents short-form production output as `final_video.mp4`",
        "defaults `run_production` to `RenderMode.PREVIEW`",
        "writes `preview_video.mp4` by default",
        "only writes `publish_video.mp4` when publish mode is used",
        "NOT_FOR_PUBLICATION",
        "publication_eligible: false",
    ]:
        assert term in content


def test_p24_output_inventory_documents_missing_creator_ready_assets_and_platform_gaps() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "content_package.json",
        "title options",
        "first-frame options",
        "thumbnail concepts",
        "upload description",
        "hashtags",
        "pinned comment",
        "platform-specific caption variants",
        "retention score",
        "hook score",
        "CTA/comment-trigger options",
        "rights clearance status",
        "monetization risk report",
        "originality assessment",
        "source attribution checklist",
        "music license note",
        "platform export folders",
        "human editorial review status",
        "publish-readiness manifest",
        "YouTube Shorts",
        "YouTube long-form",
        "TikTok",
        "Instagram Reels",
        "Facebook Reels",
        "X/Twitter",
        "run identity",
        "platform suitability",
        "next actions",
    ]:
        assert term in content


def test_p24_output_inventory_documents_stop_conditions_guardrails_and_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "generated outputs are described as publish-ready without review",
        "`preview_video.mp4` is treated as publication eligible",
        "`final_video.mp4` naming is used without clarifying",
        "`image_sources.json` is treated as copyright clearance",
        "web image filter is treated as legal approval",
        "extracted broadcast footage is treated as rights-cleared",
        "background music file is treated as licensed for every platform",
        "platform upload is implied",
        "monetization approval is implied",
        "human editorial review is skipped",
        "workflow gate bypass is requested",
        "No automatic approval.",
        "No automatic release.",
        "No automatic rendering.",
        "No automatic publishing.",
        "No automatic upload.",
        "No automatic rights clearance.",
        "No automatic monetization approval.",
        "No automatic legal approval.",
        "No automatic platform export.",
        "No automatic external distribution.",
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
