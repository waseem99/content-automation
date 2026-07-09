from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.export_readiness import (
    COMMON_METADATA_FIELDS,
    COMMON_REVIEW_STATUS_FIELDS,
    SUPPORTED_EXPORT_PLATFORMS,
    build_cross_platform_export_readiness_report,
    validate_cross_platform_export_packs,
)
from src.short_form_exports import SHORT_FORM_REQUIRED_FILES, build_short_form_export_packs
from src.x_twitter_export import X_TWITTER_REQUIRED_FILES, build_x_twitter_export_pack
from src.youtube_shorts_export import YOUTUBE_SHORTS_REQUIRED_FILES, build_youtube_shorts_export_pack


pytestmark = pytest.mark.integration

DOC = Path("docs/operations/p27-step-05.md")
EXAMPLE = Path("docs/operations/p27-cross-platform-readiness-example.json")


def _build_pack_map() -> dict[str, dict[str, object]]:
    topic = "Neymar 2014 World Cup injury and comeback pressure"
    packs: dict[str, dict[str, object]] = {
        "youtube_shorts": build_youtube_shorts_export_pack(topic, subject="Neymar"),
        "x_twitter": build_x_twitter_export_pack(topic, subject="Neymar"),
    }
    packs.update(build_short_form_export_packs(topic, subject="Neymar"))
    return packs


def test_p27_cross_platform_doc_references_scope_inputs_and_outputs() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #329. Closes #354 after the PR merges.",
        "docs/operations/p24-readiness-report.md",
        "docs/operations/p25-readiness-report.md",
        "docs/operations/p26-readiness-report.md",
        "docs/operations/p27-step-01.md",
        "docs/operations/p27-step-02.md",
        "docs/operations/p27-step-03.md",
        "docs/operations/p27-step-04.md",
        "src/youtube_shorts_export.py",
        "src/short_form_exports.py",
        "src/x_twitter_export.py",
        "src/export_readiness.py",
        "docs/operations/p27-cross-platform-readiness-example.json",
        "tests/integration/test_p27_step_05.py",
        "youtube_shorts",
        "tiktok",
        "instagram_reels",
        "facebook_reels",
        "x_twitter",
    ]:
        assert term in content


def test_p27_cross_platform_doc_explains_manual_workflow_and_validation_rules() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "YouTube long-form is intentionally not included",
        "Required platform packs",
        "Required files",
        "Platform names",
        "Metadata fields",
        "Review status fields",
        "Risk carry-through",
        "Risk notes",
        "Platform-specific caveats",
        "Publish gating",
        "is_ready_for_manual_review: true",
        "is_publish_ready: false",
        "Manual-review readiness is not publishing approval.",
        "Review generated copy and metadata per platform.",
        "Confirm P26 rights, monetization, source attribution, music, and originality status.",
        "Complete P29 editorial approval before any publish-ready state.",
    ]:
        assert term in content


def test_p27_cross_platform_readiness_report_validates_all_required_outputs() -> None:
    report = build_cross_platform_export_readiness_report(
        "Neymar 2014 World Cup injury and comeback pressure",
        subject="Neymar",
    )

    assert report["schema_version"] == "p27.cross_platform_export_readiness.v1"
    assert report["platforms"] == list(SUPPORTED_EXPORT_PLATFORMS)
    assert report["publish_allowed"] is False
    assert report["review_required"] is True
    assert report["is_ready_for_manual_review"] is True
    assert report["is_publish_ready"] is False
    assert report["errors"] == []

    results = report["platform_results"]
    assert set(results) == set(SUPPORTED_EXPORT_PLATFORMS)
    assert set(results["youtube_shorts"]["checked_files"]) == set(YOUTUBE_SHORTS_REQUIRED_FILES)
    assert set(results["tiktok"]["checked_files"]) == set(SHORT_FORM_REQUIRED_FILES)
    assert set(results["instagram_reels"]["checked_files"]) == set(SHORT_FORM_REQUIRED_FILES)
    assert set(results["facebook_reels"]["checked_files"]) == set(SHORT_FORM_REQUIRED_FILES)
    assert set(results["x_twitter"]["checked_files"]) == set(X_TWITTER_REQUIRED_FILES)

    for result in results.values():
        assert result["is_ready_for_manual_review"] is True
        assert result["publish_allowed"] is False
        assert result["review_required"] is True
        assert result["errors"] == []


def test_p27_cross_platform_validator_catches_missing_required_files() -> None:
    packs = _build_pack_map()
    del packs["tiktok"]["files"]["caption.txt"]  # type: ignore[index]

    report = validate_cross_platform_export_packs(packs)  # type: ignore[arg-type]

    assert report["is_ready_for_manual_review"] is False
    assert "tiktok: missing required file caption.txt" in report["errors"]
    assert report["is_publish_ready"] is False
    assert report["publish_allowed"] is False


def test_p27_cross_platform_validator_catches_missing_or_inconsistent_risk_notes() -> None:
    packs = _build_pack_map()
    packs["x_twitter"]["files"]["risk_note.txt"]["content"] = "No caveats here."  # type: ignore[index]

    report = validate_cross_platform_export_packs(packs)  # type: ignore[arg-type]

    assert report["is_ready_for_manual_review"] is False
    assert "x_twitter: risk note missing publish_allowed false" in report["errors"]
    assert "x_twitter: missing factual/stat caveat" in report["errors"]


def test_p27_cross_platform_validator_catches_publish_ready_or_allowed_blocked_content() -> None:
    packs = _build_pack_map()
    packs["facebook_reels"]["review_status"]["export_status"] = "publish_ready"  # type: ignore[index]
    packs["facebook_reels"]["metadata"]["publish_allowed"] = True  # type: ignore[index]

    report = validate_cross_platform_export_packs(packs)  # type: ignore[arg-type]

    assert report["is_ready_for_manual_review"] is False
    assert "facebook_reels: metadata publish_allowed must be false" in report["errors"]
    assert "facebook_reels: blocked content must not appear publish-ready" in report["errors"]
    assert report["is_publish_ready"] is False


def test_p27_cross_platform_validator_checks_metadata_review_status_and_risk_carrythrough() -> None:
    packs = _build_pack_map()
    report = validate_cross_platform_export_packs(packs)  # type: ignore[arg-type]

    assert report["errors"] == []

    for platform, pack in packs.items():
        metadata = pack["metadata"]  # type: ignore[index]
        review_status = pack["review_status"]  # type: ignore[index]
        assert COMMON_METADATA_FIELDS <= set(metadata)  # type: ignore[arg-type]
        assert COMMON_REVIEW_STATUS_FIELDS <= set(review_status)  # type: ignore[arg-type]
        assert metadata["platform"] == platform  # type: ignore[index]
        assert review_status["platform"] == platform  # type: ignore[index]
        assert metadata["blocking_reasons"] == review_status["blocking_reasons"]  # type: ignore[index]
        assert metadata["required_actions"] == review_status["required_actions"]  # type: ignore[index]
        assert metadata["publish_allowed"] is False  # type: ignore[index]
        assert review_status["publish_allowed"] is False  # type: ignore[index]


def test_p27_cross_platform_example_contains_readiness_evidence() -> None:
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    assert example["schema_version"] == "p27.cross_platform_export_readiness.v1"
    assert example["platforms"] == list(SUPPORTED_EXPORT_PLATFORMS)
    assert example["publish_allowed"] is False
    assert example["review_required"] is True
    assert example["is_ready_for_manual_review"] is True
    assert example["is_publish_ready"] is False
    assert example["errors"] == []
    assert len(example["manual_publishing_workflow"]) == 4

    for platform in SUPPORTED_EXPORT_PLATFORMS:
        result = example["platform_results"][platform]
        assert result["platform"] == platform
        assert result["is_ready_for_manual_review"] is True
        assert result["publish_allowed"] is False
        assert result["review_required"] is True
        assert result["errors"] == []


def test_p27_cross_platform_readiness_is_deterministic_and_rejects_invalid_inputs() -> None:
    first = build_cross_platform_export_readiness_report("World Cup 2026 pressure index", subject="World Cup 2026")
    second = build_cross_platform_export_readiness_report("World Cup 2026 pressure index", subject="World Cup 2026")
    assert first == second

    with pytest.raises(ValueError):
        build_cross_platform_export_readiness_report("   ")


def test_p27_cross_platform_stop_conditions_and_guardrails_are_documented() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "validation is treated as publishing approval",
        "`publish_allowed` defaults to `true`",
        "blocked content is marked `publish_ready`",
        "P26 publish-block rules are ignored",
        "P29 editorial approval is bypassed",
        "platform credentials are requested or stored",
        "platform API upload checks are introduced",
        "live post previews are introduced",
        "external rendered videos are committed",
        "secret values are committed",
        "workflow gate bypass is requested",
        "No platform upload.",
        "No platform API checks.",
        "No live post previews.",
        "No platform credentials.",
        "No external video asset commits.",
        "No secret values.",
        "No automatic publish approval.",
        "No automatic rights clearance.",
        "No automatic monetization approval.",
        "No automatic factual/stat approval.",
        "No automatic editorial approval.",
        "No bypass of P26 publish-block rules.",
        "No bypass of P29 editorial governance.",
        "No workflow gate bypass.",
        "No implementation without scoped issue and PR.",
        "No merge without exact-head CI.",
    ]:
        assert term in content
