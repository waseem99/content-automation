from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


DOC = Path("docs/operations/p26-step-01.md")
HARNESS = Path(".github/workflows/p1-acceptance-harness.yml")


def test_p26_asset_rights_classification_references_inputs_and_scope() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #328. Closes #344 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p24-step-03.md",
        "src/content_package.py",
        "src/title_options.py",
        "src/visual_concepts.py",
        "src/retention_score.py",
        "src/cta_library.py",
        ".github/workflows/p1-acceptance-harness.yml",
        "This rights classification model is documentation-only.",
        "clear copyrights",
        "provide legal advice",
        "predict Content ID claims",
        "predict copyright strikes",
        "verify licenses automatically",
        "fetch license pages",
        "inspect private platform accounts",
        "approve monetization",
        "approve publishing",
        "upload to any platform",
        "publish content",
        "bypass workflow gates",
    ]:
        assert term in content


def test_p26_asset_rights_classification_documents_risk_levels_and_required_fields() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "low",
        "medium",
        "high",
        "blocked_until_review",
        "not_applicable",
        "asset_role",
        "default_risk_level",
        "review_action",
        "allowed_evidence",
        "blocked_evidence",
        "publish_blocking_by_default",
        "notes",
    ]:
        assert term in content


def test_p26_asset_rights_classification_includes_required_asset_roles() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "`source_video`",
        "`broadcast_clip`",
        "`extracted_clip`",
        "`web_image`",
        "`ai_image`",
        "`voiceover`",
        "`music`",
        "`font`",
        "`logo`",
        "`overlay`",
        "`script`",
        "`stat`",
        "`concept_yaml`",
        "`manifest`",
        "`production_plan`",
        "`caption_file`",
        "`thumbnail_concept`",
        "`title_option`",
        "`cta_option`",
        "`retention_score_report`",
    ]:
        assert term in content


def test_p26_asset_rights_classification_marks_high_risk_assets_blocking_by_default() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "`source_video` | `high` | yes",
        "`broadcast_clip` | `blocked_until_review` | yes",
        "`extracted_clip` | `blocked_until_review` | yes",
        "`music` | `high` | yes",
        "`logo` | `high` | yes",
        "Treat football broadcast footage as not rights-cleared unless explicit rights or legal/editorial clearance exists.",
        "Review source footage rights, clip duration, transformative use, commentary layer, and platform risk.",
        "Confirm music license per platform; do not assume one license covers YouTube, TikTok, Instagram, Facebook, and X/Twitter.",
        "Confirm rights to use club, league, tournament, sponsor, platform, or brand marks.",
    ]:
        assert term in content


def test_p26_asset_rights_classification_documents_allowed_and_blocked_evidence_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "asset role",
        "asset path",
        "source URL",
        "source domain",
        "license name or summary",
        "attribution-needed status",
        "reviewer role",
        "review status",
        "non-sensitive decision summary",
        "issue or PR reference",
        "CI run identifier",
        "merge commit reference",
        "paid license documents containing private account data",
        "private account screenshots",
        "platform account IDs not already public",
        "private creator contracts",
        "private customer data",
        "raw legal correspondence",
        "secret values",
        "tokens",
        "private runtime values",
        "unredacted invoices",
        "external package exports",
    ]:
        assert term in content


def test_p26_asset_rights_classification_includes_required_examples() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Football match footage",
        "Football match footage, broadcast highlights, extracted clips, and match stills must default to `blocked_until_review`.",
        "confirm source ownership or permission",
        "confirm whether use is allowed on the target platform",
        "Wikimedia images",
        "Wikimedia images may vary by license and must default to `medium` until checked.",
        "verify the exact license page",
        "capture attribution requirements",
        "Pexels and Pixabay images",
        "Pexels and Pixabay images may be lower risk than unfiltered web images, but they still require review.",
        "confirm no trademark, logo, or identifiable person issue remains",
        "AI visuals",
        "AI visuals default to `medium` and remain publish-blocking until reviewed.",
        "confirm the image is not presented as real footage",
        "Background music",
        "Background music defaults to `high` and publish-blocking.",
        "verify target platform coverage",
        "keep music blocked if a platform-specific license cannot be confirmed",
    ]:
        assert term in content


def test_p26_asset_rights_classification_documents_future_risk_report_linkage() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Connection to future risk report",
        "P26-02 should use this classification model to populate `monetization_risk_report.json`",
        "`asset_role`",
        "`default_risk_level`",
        "`review_required`",
        "`publish_blocking_by_default`",
        "`required_actions`",
        "`blocking_reasons`",
        "`evidence_allowed`",
        "`evidence_blocked`",
    ]:
        assert term in content


def test_p26_asset_rights_classification_documents_stop_conditions_guardrails_and_ci() -> None:
    content = DOC.read_text(encoding="utf-8")
    harness = HARNESS.read_text(encoding="utf-8")
    for term in [
        "broadcast clips are marked low risk by default",
        "extracted clips are marked rights-cleared by default",
        "unverified music is marked low risk by default",
        "web image filtering is treated as legal clearance",
        "`image_sources.json` is treated as copyright clearance",
        "a retention score is treated as rights clearance",
        "platform upload is introduced",
        "monetization approval is implied",
        "legal approval is implied",
        "workflow gate bypass is requested",
        "No automated legal clearance.",
        "No copyright claim prediction.",
        "No Content ID prediction.",
        "No automatic license verification.",
        "No automatic rights clearance.",
        "No automatic monetization approval.",
        "No automatic publishing approval.",
        "No automatic upload.",
        "No automatic publishing.",
        "No secret values in evidence.",
        "No private runtime values in notes.",
        "No customer data exports.",
        "No external package exports.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content

    assert "tests/integration/test_p26_step_*.py" in harness
