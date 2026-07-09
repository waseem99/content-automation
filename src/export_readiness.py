"""Cross-platform export readiness validation helpers.

These helpers validate review-only export pack manifests across P27 platforms.
They do not upload content, render previews, call platform APIs, or approve
publishing. A passing readiness report means the packs are complete enough for
manual review, not publish-ready.
"""

from __future__ import annotations

from typing import Any

from src.short_form_exports import SHORT_FORM_PLATFORMS, SHORT_FORM_REQUIRED_FILES, build_short_form_export_packs
from src.x_twitter_export import X_TWITTER_REQUIRED_FILES, build_x_twitter_export_pack
from src.youtube_shorts_export import YOUTUBE_SHORTS_REQUIRED_FILES, build_youtube_shorts_export_pack

SUPPORTED_EXPORT_PLATFORMS = (
    "youtube_shorts",
    "tiktok",
    "instagram_reels",
    "facebook_reels",
    "x_twitter",
)

REQUIRED_FILES_BY_PLATFORM: dict[str, tuple[str, ...]] = {
    "youtube_shorts": YOUTUBE_SHORTS_REQUIRED_FILES,
    "tiktok": SHORT_FORM_REQUIRED_FILES,
    "instagram_reels": SHORT_FORM_REQUIRED_FILES,
    "facebook_reels": SHORT_FORM_REQUIRED_FILES,
    "x_twitter": X_TWITTER_REQUIRED_FILES,
}

COMMON_METADATA_FIELDS = {
    "schema_version",
    "package_id",
    "platform",
    "export_directory",
    "content_type",
    "video_asset_path",
    "copy_asset_paths",
    "review_status_path",
    "source_package_path",
    "monetization_risk_report_path",
    "source_attribution_path",
    "publish_allowed",
    "review_required",
    "blocking_reasons",
    "required_actions",
    "created_by_step",
    "planned_epic",
    "p26_decision_state",
}

COMMON_REVIEW_STATUS_FIELDS = {
    "platform",
    "package_id",
    "export_status",
    "publish_allowed",
    "p26_review_status",
    "p29_editorial_status",
    "rights_status",
    "monetization_status",
    "source_attribution_status",
    "originality_status",
    "blocking_reasons",
    "required_actions",
    "reviewer_role",
    "notes",
}

RISK_FILES_BY_PLATFORM = {
    "youtube_shorts": ("risk_note.txt", "rights_note.txt"),
    "tiktok": ("music_risk_note.txt", "publishing_note.txt"),
    "instagram_reels": ("music_risk_note.txt", "publishing_note.txt"),
    "facebook_reels": ("music_risk_note.txt", "publishing_note.txt"),
    "x_twitter": ("risk_note.txt",),
}


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def _file_content(pack: dict[str, Any], filename: str) -> str:
    file_data = pack.get("files", {}).get(filename, {})
    return str(file_data.get("content", ""))


def validate_platform_export_pack(pack: dict[str, Any]) -> dict[str, Any]:
    """Validate one platform export pack for manual-review readiness."""

    errors: list[str] = []
    warnings: list[str] = []

    platform = str(pack.get("platform", ""))
    _require(platform in SUPPORTED_EXPORT_PLATFORMS, errors, f"unsupported platform: {platform or '<missing>'}")

    required_files = REQUIRED_FILES_BY_PLATFORM.get(platform, ())
    files = pack.get("files", {})
    metadata = pack.get("metadata", {})
    review_status = pack.get("review_status", {})

    for filename in required_files:
        _require(filename in files, errors, f"{platform}: missing required file {filename}")

    _require(set(pack.get("required_files", [])) == set(required_files), errors, f"{platform}: required_files mismatch")
    _require(COMMON_METADATA_FIELDS <= set(metadata), errors, f"{platform}: missing common metadata fields")
    _require(COMMON_REVIEW_STATUS_FIELDS <= set(review_status), errors, f"{platform}: missing common review status fields")

    _require(metadata.get("platform") == platform, errors, f"{platform}: metadata platform mismatch")
    _require(review_status.get("platform") == platform, errors, f"{platform}: review status platform mismatch")
    _require(pack.get("publish_allowed") is False, errors, f"{platform}: pack publish_allowed must be false")
    _require(metadata.get("publish_allowed") is False, errors, f"{platform}: metadata publish_allowed must be false")
    _require(review_status.get("publish_allowed") is False, errors, f"{platform}: review_status publish_allowed must be false")
    _require(pack.get("review_required") is True, errors, f"{platform}: pack review_required must be true")
    _require(metadata.get("review_required") is True, errors, f"{platform}: metadata review_required must be true")

    export_status = review_status.get("export_status")
    _require(export_status != "publish_ready", errors, f"{platform}: blocked content must not appear publish-ready")
    _require(export_status in {"blocked_until_review", "generated_pending_review", "export_candidate_after_review"}, errors, f"{platform}: unexpected export_status {export_status}")

    blocking_reasons = metadata.get("blocking_reasons", [])
    required_actions = metadata.get("required_actions", [])
    _require(bool(blocking_reasons), errors, f"{platform}: blocking_reasons must be present")
    _require(bool(required_actions), errors, f"{platform}: required_actions must be present")
    _require(blocking_reasons == review_status.get("blocking_reasons"), errors, f"{platform}: blocking reasons not carried into review status")
    _require(required_actions == review_status.get("required_actions"), errors, f"{platform}: required actions not carried into review status")

    combined_risk_note = "\n".join(_file_content(pack, filename) for filename in RISK_FILES_BY_PLATFORM.get(platform, ()))
    _require("publish_allowed: false" in combined_risk_note, errors, f"{platform}: risk note missing publish_allowed false")
    _require("review_required: true" in combined_risk_note or platform == "youtube_shorts", errors, f"{platform}: risk note missing review_required true")
    _require("P29" in combined_risk_note or "editorial" in combined_risk_note.lower(), errors, f"{platform}: risk note missing editorial/P29 caveat")

    if platform in SHORT_FORM_PLATFORMS:
        _require(
            "Do not assume one music license works across TikTok, Instagram Reels, and Facebook Reels."
            in _file_content(pack, "music_risk_note.txt"),
            errors,
            f"{platform}: missing platform-specific music risk caveat",
        )
    if platform == "x_twitter":
        _require(
            "Stats, rights, and source claims are not automatically cleared." in _file_content(pack, "risk_note.txt"),
            errors,
            "x_twitter: missing factual/stat caveat",
        )

    if export_status == "export_candidate_after_review":
        warnings.append(f"{platform}: export candidate still requires final P29 approval before publishing")

    return {
        "platform": platform,
        "is_ready_for_manual_review": not errors,
        "publish_allowed": False,
        "review_required": True,
        "checked_files": list(required_files),
        "errors": errors,
        "warnings": warnings,
    }


def validate_cross_platform_export_packs(packs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Validate all required P27 platform export packs."""

    platform_results = {platform: validate_platform_export_pack(packs.get(platform, {})) for platform in SUPPORTED_EXPORT_PLATFORMS}
    missing_platforms = [platform for platform in SUPPORTED_EXPORT_PLATFORMS if platform not in packs]
    errors = [f"missing platform pack: {platform}" for platform in missing_platforms]
    for result in platform_results.values():
        errors.extend(result["errors"])

    return {
        "schema_version": "p27.cross_platform_export_readiness.v1",
        "platforms": list(SUPPORTED_EXPORT_PLATFORMS),
        "publish_allowed": False,
        "review_required": True,
        "is_ready_for_manual_review": not errors,
        "is_publish_ready": False,
        "platform_results": platform_results,
        "errors": errors,
        "manual_publishing_workflow": [
            "Review generated copy and metadata per platform.",
            "Confirm P26 rights, monetization, source attribution, music, and originality status.",
            "Complete P29 editorial approval before any publish-ready state.",
            "Only then may a human operator manually prepare platform uploads outside this validation helper.",
        ],
    }


def build_cross_platform_export_readiness_report(
    topic: str,
    *,
    subject: str | None = None,
    publish_block_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and validate deterministic review-only export packs for P27 platforms."""

    packs: dict[str, dict[str, Any]] = {
        "youtube_shorts": build_youtube_shorts_export_pack(
            topic,
            subject=subject,
            publish_block_decision=publish_block_decision,
        ),
        "x_twitter": build_x_twitter_export_pack(
            topic,
            subject=subject,
            publish_block_decision=publish_block_decision,
        ),
    }
    packs.update(
        build_short_form_export_packs(
            topic,
            subject=subject,
            publish_block_decision=publish_block_decision,
        )
    )
    report = validate_cross_platform_export_packs(packs)
    report["source_topic"] = " ".join(topic.strip().split())
    report["subject"] = " ".join((subject or topic).strip().split())
    return report
