from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p24-step-05.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p24_operator_workflow_references_inputs_and_is_documentation_only() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #326. Closes #336 after the PR merges.",
        "docs/operations/p24-step-01.md",
        "docs/operations/p24-step-02.md",
        "docs/operations/p24-step-03.md",
        "docs/operations/p24-step-04.md",
        "src/content_package.py",
        "docs/operations/p24-content-package-short-example.json",
        "docs/operations/p24-content-package-explainer-example.json",
        "tests/integration/test_p24_step_05.py",
        "This operator workflow is documentation-only.",
        "approve content",
        "approve rights",
        "approve monetization",
        "approve editorial status",
        "generate packaging assets",
        "generate retention scores",
        "generate platform export folders",
        "render videos",
        "upload to any platform",
        "publish content",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p24_operator_workflow_documents_review_sequence_and_field_meanings() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Locate the generated `content_package.json`",
        "Confirm `schema_version` is `p24.content_package.v1`",
        "Confirm `content_status` is `package_generated`",
        "Review `run_identity`",
        "Review `source_assets`",
        "Review `generated_assets`",
        "Review `platform_suitability`",
        "Review `missing_assets`",
        "Review `packaging` and `retention`",
        "Review `rights_and_monetization`",
        "confirm `publish_allowed` remains `false`",
        "Review `exports`",
        "Review `editorial_review`",
        "Review `next_actions`",
        "Review `guardrails`",
        "Input and source evidence that may carry rights, factual, or lineage risk",
        "P25 title, first-frame, thumbnail, hook, and CTA placeholders",
        "P26 risk and rights placeholders; must block publish until reviewed",
        "P27 platform export placeholders; paths are not real exports until generated",
        "P29 approval state and blockers",
    ]:
        assert term in content


def test_p24_operator_workflow_documents_safe_and_unsafe_statuses() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "package_generated",
        "draft_contract_example",
        "pending_p25",
        "pending_p26",
        "pending_p27",
        "pending_p29",
        "not_approved",
        "not_publish_ready",
        "review_required",
        "review_only",
        "publish_ready",
        "approved_for_upload",
        "rights_cleared",
        "monetization_approved",
        "editorial_approved",
        "platform_export_ready",
        "publication_eligible: true",
    ]:
        assert term in content


def test_p24_operator_workflow_documents_short_and_explainer_checklists() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Short review checklist",
        "`production_plan.json` exists and matches the intended topic",
        "`manifest.json` exists and references the selected clips",
        "`clip_*.mp4` entries are treated as unreviewed source footage",
        "`preview_video.mp4` is review-only and not publication eligible",
        "`publish_video.mp4`, if present, is still not upload-approved",
        "`image_sources.json` is source evidence, not copyright clearance",
        "title options are missing until P25",
        "first-frame options are missing until P25",
        "retention score is missing until P25",
        "monetization risk report is missing until P26",
        "platform export folders are missing until P27",
        "editorial approval is missing until P29",
        "Explainer review checklist",
        "`explainer_plan.json` exists and matches the intended concept",
        "`concept.yaml` exists when available",
        "clip pool `manifest.json` exists when available",
        "`final_video.mp4` is not automatically publish-ready",
        "factual source review is still required",
        "rights and originality review are still required",
        "true YouTube long-form readiness still requires P28 planning",
    ]:
        assert term in content


def test_p24_operator_workflow_documents_package_not_publish_approval_and_handoffs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Package is not publish approval",
        "Creating `content_package.json` means only that the current run has a structured review manifest.",
        "the content is safe to publish",
        "the content is approved for YouTube",
        "the content is approved for TikTok",
        "the content is approved for Instagram",
        "the content is approved for Facebook",
        "the content is approved for X/Twitter",
        "broadcast footage is rights-cleared",
        "web images are copyright-cleared",
        "music is licensed for all platforms",
        "claims and stats are fact-checked",
        "the video is monetization-ready",
        "an editor has approved the package",
        "A package may move to P25 when",
        "A package may move to P26 when",
        "A package may move to P27 when",
        "A package may move to P29 when",
        "`publish_allowed` is still `false`",
        "approval state remains `not_approved` before review",
    ]:
        assert term in content


def test_p24_operator_workflow_documents_stop_conditions_guardrails_and_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "package creation is treated as publish approval",
        "`preview_video.mp4` is selected for upload",
        "`image_sources.json` is treated as copyright clearance",
        "broadcast clips are treated as rights-cleared by default",
        "music is assumed safe across every platform",
        "platform export folders are implied before P27",
        "editorial approval is implied before P29",
        "monetization approval is implied before P26",
        "upload or publishing is introduced",
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
