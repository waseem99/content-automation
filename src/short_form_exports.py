"""Deterministic TikTok, Instagram Reels, and Facebook Reels export helpers.

These helpers build review-only short-form export manifests. They do not render
videos, upload to platforms, automate music licensing, connect platform APIs, or
mark any output publish-ready.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from src.cta_library import build_cta_options
from src.visual_concepts import build_visual_concepts

ShortFormPlatform = Literal["tiktok", "instagram_reels", "facebook_reels"]

SHORT_FORM_PLATFORMS: tuple[ShortFormPlatform, ...] = (
    "tiktok",
    "instagram_reels",
    "facebook_reels",
)

SHORT_FORM_REQUIRED_FILES = (
    "video.mp4",
    "caption.txt",
    "hashtags.txt",
    "cover_notes.txt",
    "music_risk_note.txt",
    "publishing_note.txt",
    "metadata.json",
    "review_status.json",
)

PLATFORM_CONFIG: dict[ShortFormPlatform, dict[str, Any]] = {
    "tiktok": {
        "export_directory": "exports/tiktok/",
        "caption_style": "fast_hook_direct_question",
        "hashtags": ("#football", "#footballtiktok", "#soccer", "#fyp"),
        "cover_focus": "Use the strongest first-frame hook with minimal text and no unsupported claims.",
        "publishing_context": "TikTok export is review-only and must not assume trending-sound or music usage rights.",
    },
    "instagram_reels": {
        "export_directory": "exports/instagram_reels/",
        "caption_style": "polished_social_caption",
        "hashtags": ("#football", "#reels", "#soccerreels", "#footballstories"),
        "cover_focus": "Use a clean cover frame that is readable in grid view and story reshares.",
        "publishing_context": "Instagram Reels export is review-only and must keep collaborator, music, and asset rights unresolved until reviewed.",
    },
    "facebook_reels": {
        "export_directory": "exports/facebook_reels/",
        "caption_style": "context_first_caption",
        "hashtags": ("#football", "#facebookreels", "#soccer", "#sportsvideo"),
        "cover_focus": "Use a clear first frame that works for feed preview and older audience context.",
        "publishing_context": "Facebook Reels export is review-only and must keep monetization and music risk visible.",
    },
}

DEFAULT_BLOCKING_REASONS = (
    "P26 monetization and rights review required.",
    "Platform-specific music rights review required.",
    "P29 editorial approval required.",
)

DEFAULT_REQUIRED_ACTIONS = (
    "Confirm the caption, hashtags, cover notes, and publishing note match the script and rendered video.",
    "Verify music, footage, image, logo, and source attribution rights for each platform separately.",
    "Complete P29 editorial approval before any publish-ready state.",
)


def _clean(value: str, field_name: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _list_or_default(values: Any, default: tuple[str, ...]) -> list[str]:
    if not values:
        return list(default)
    return [str(value) for value in values]


def _text_file(path: str, content: str) -> dict[str, str]:
    return {"path": path, "content_type": "text/plain", "content": content}


def _json_file(path: str, content: dict[str, Any]) -> dict[str, str]:
    return {"path": path, "content_type": "application/json", "content": json.dumps(content, indent=2, sort_keys=True)}


def _caption(*, platform: ShortFormPlatform, topic: str, subject: str, cta_text: str) -> str:
    if platform == "tiktok":
        return f"{subject}: this football story still starts arguments. {cta_text}"
    if platform == "instagram_reels":
        return f"{topic}\n\nA short football story for review before publishing. {cta_text}"
    return f"{topic}\n\nContext first, hype second. {cta_text}"


def _cover_notes(*, config: dict[str, Any], first_frame_option: dict[str, Any]) -> str:
    risk_notes = "\n".join(f"- {note}" for note in first_frame_option["risk_notes"])
    return "\n".join(
        [
            f"Cover focus: {config['cover_focus']}",
            f"Selected first-frame concept: {first_frame_option['concept_id']}",
            f"Suggested text: {first_frame_option['suggested_text']}",
            f"Layout: {first_frame_option['visual_layout']}",
            "",
            "Review notes:",
            risk_notes,
        ]
    )


def _music_risk_note(*, platform: ShortFormPlatform, decision_state: str) -> str:
    return "\n".join(
        [
            f"{platform} music risk note",
            "Do not assume one music license works across TikTok, Instagram Reels, and Facebook Reels.",
            "Confirm platform-specific music, sound, voiceover, footage, and image rights before any publish-ready state.",
            f"P26 decision state: {decision_state}",
            "P29 editorial status: missing",
            "publish_allowed: false",
            "review_required: true",
        ]
    )


def _publishing_note(*, config: dict[str, Any], blocking_reasons: list[str], required_actions: list[str]) -> str:
    reason_lines = "\n".join(f"- {reason}" for reason in blocking_reasons)
    action_lines = "\n".join(f"- {action}" for action in required_actions)
    return "\n".join(
        [
            config["publishing_context"],
            "This export pack is not an upload instruction, music clearance, monetization approval, or publish approval.",
            "publish_allowed: false",
            "review_required: true",
            "",
            "Blocking reasons:",
            reason_lines,
            "",
            "Required actions:",
            action_lines,
        ]
    )


def build_short_form_export_pack(
    platform: ShortFormPlatform,
    topic: str,
    *,
    subject: str | None = None,
    package_id: str | None = None,
    video_asset_path: str = "renders/shorts/neymar-2014-comeback-pressure.mp4",
    source_package_path: str = "content_package.json",
    monetization_risk_report_path: str = "monetization_risk_report.json",
    source_attribution_path: str = "source_attribution.json",
    publish_block_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one deterministic, review-only short-form platform export pack."""

    if platform not in SHORT_FORM_PLATFORMS:
        raise ValueError("platform must be one of: tiktok, instagram_reels, facebook_reels")

    topic_text = _clean(topic, "topic")
    subject_text = _clean(subject or topic_text, "subject")
    package_id_text = _clean(package_id or f"pkg-{platform}-export-example", "package_id")
    video_path_text = _clean(video_asset_path, "video_asset_path")
    source_package_text = _clean(source_package_path, "source_package_path")
    risk_report_text = _clean(monetization_risk_report_path, "monetization_risk_report_path")
    attribution_text = _clean(source_attribution_path, "source_attribution_path")

    config = PLATFORM_CONFIG[platform]
    export_directory = config["export_directory"]
    cta_option = build_cta_options(topic_text, subject=subject_text, content_type="short")[0]
    first_frame_option = build_visual_concepts(topic_text, subject=subject_text, content_type="short")[
        "first_frame_options"
    ][0]

    decision = publish_block_decision or {}
    decision_state = str(decision.get("decision_state") or "review_required")
    blocking_reasons = _list_or_default(decision.get("blocking_reasons"), DEFAULT_BLOCKING_REASONS)
    required_actions = _list_or_default(decision.get("required_actions"), DEFAULT_REQUIRED_ACTIONS)

    metadata = {
        "schema_version": "p27.short_form_export_pack.v1",
        "package_id": package_id_text,
        "platform": platform,
        "export_directory": export_directory,
        "content_type": "short",
        "video_asset_path": video_path_text,
        "copy_asset_paths": {
            "caption": f"{export_directory}caption.txt",
            "hashtags": f"{export_directory}hashtags.txt",
            "cover_notes": f"{export_directory}cover_notes.txt",
            "music_risk_note": f"{export_directory}music_risk_note.txt",
            "publishing_note": f"{export_directory}publishing_note.txt",
        },
        "review_status_path": f"{export_directory}review_status.json",
        "source_package_path": source_package_text,
        "monetization_risk_report_path": risk_report_text,
        "source_attribution_path": attribution_text,
        "publish_allowed": False,
        "review_required": True,
        "blocking_reasons": blocking_reasons,
        "required_actions": required_actions,
        "created_by_step": "P27-03",
        "planned_epic": "P27",
        "caption_style": config["caption_style"],
        "p25_packaging_sources": {
            "cta_id": cta_option["cta_id"],
            "first_frame_concept_id": first_frame_option["concept_id"],
        },
        "p26_decision_state": decision_state,
    }

    review_status = {
        "platform": platform,
        "package_id": package_id_text,
        "export_status": "blocked_until_review",
        "publish_allowed": False,
        "p26_review_status": "required",
        "p29_editorial_status": "missing",
        "rights_status": "review_required",
        "monetization_status": "review_required",
        "source_attribution_status": "review_required",
        "music_license_status": "platform_specific_review_required",
        "originality_status": "review_required",
        "blocking_reasons": blocking_reasons,
        "required_actions": required_actions,
        "reviewer_role": "publishing operator",
        "notes": [
            "Short-form export pack is review-only.",
            "Music and asset rights must be reviewed per platform.",
            "P29 editorial approval remains required before any publish-ready state.",
        ],
    }

    files: dict[str, dict[str, Any]] = {
        "video.mp4": {
            "path": f"{export_directory}video.mp4",
            "content_type": "video/mp4",
            "source_asset_path": video_path_text,
            "status": "reference_only_not_committed",
        },
        "caption.txt": _text_file(
            f"{export_directory}caption.txt",
            _caption(platform=platform, topic=topic_text, subject=subject_text, cta_text=cta_option["cta_text"]),
        ),
        "hashtags.txt": _text_file(f"{export_directory}hashtags.txt", "\n".join(config["hashtags"])),
        "cover_notes.txt": _text_file(
            f"{export_directory}cover_notes.txt",
            _cover_notes(config=config, first_frame_option=first_frame_option),
        ),
        "music_risk_note.txt": _text_file(
            f"{export_directory}music_risk_note.txt",
            _music_risk_note(platform=platform, decision_state=decision_state),
        ),
        "publishing_note.txt": _text_file(
            f"{export_directory}publishing_note.txt",
            _publishing_note(config=config, blocking_reasons=blocking_reasons, required_actions=required_actions),
        ),
        "metadata.json": _json_file(f"{export_directory}metadata.json", metadata),
        "review_status.json": _json_file(f"{export_directory}review_status.json", review_status),
    }

    return {
        "schema_version": "p27.short_form_export_pack.v1",
        "package_id": package_id_text,
        "platform": platform,
        "export_directory": export_directory,
        "required_files": list(SHORT_FORM_REQUIRED_FILES),
        "publish_allowed": False,
        "review_required": True,
        "source_inputs": {
            "topic": topic_text,
            "subject": subject_text,
            "source_package_path": source_package_text,
            "monetization_risk_report_path": risk_report_text,
            "source_attribution_path": attribution_text,
        },
        "selected_p25_fields": {
            "cta_option": cta_option,
            "first_frame_option": first_frame_option,
        },
        "metadata": metadata,
        "review_status": review_status,
        "files": files,
    }


def build_short_form_export_packs(
    topic: str,
    *,
    subject: str | None = None,
    publish_block_decision: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build deterministic review-only packs for TikTok, Instagram Reels, and Facebook Reels."""

    return {
        platform: build_short_form_export_pack(
            platform,
            topic,
            subject=subject,
            publish_block_decision=publish_block_decision,
        )
        for platform in SHORT_FORM_PLATFORMS
    }
