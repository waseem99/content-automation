"""Deterministic YouTube Shorts export pack helpers.

The helper in this module builds a review-only export manifest for YouTube
Shorts. It does not render video, call YouTube APIs, upload content, approve
rights, approve monetization, or mark anything publish-ready.
"""

from __future__ import annotations

import json
from typing import Any

from src.cta_library import build_cta_options
from src.title_options import build_title_options
from src.visual_concepts import build_visual_concepts

YOUTUBE_SHORTS_PLATFORM = "youtube_shorts"
YOUTUBE_SHORTS_EXPORT_DIRECTORY = "exports/youtube_shorts/"

YOUTUBE_SHORTS_REQUIRED_FILES = (
    "video.mp4",
    "title.txt",
    "description.txt",
    "hashtags.txt",
    "pinned_comment.txt",
    "first_frame_notes.txt",
    "risk_note.txt",
    "rights_note.txt",
    "metadata.json",
    "review_status.json",
)

DEFAULT_YOUTUBE_SHORTS_HASHTAGS = (
    "#football",
    "#footballshorts",
    "#soccer",
    "#sportsstory",
)

DEFAULT_BLOCKING_REASONS = (
    "P26 monetization and rights review required.",
    "P29 editorial approval required.",
    "Export pack is review-only and not publish approval.",
)

DEFAULT_REQUIRED_ACTIONS = (
    "Verify title, description, hashtags, pinned comment, and first-frame notes against the script.",
    "Complete P26 rights, source attribution, monetization, and originality review.",
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
    return {
        "path": path,
        "content_type": "text/plain",
        "content": content,
    }


def _json_file(path: str, content: dict[str, Any]) -> dict[str, str]:
    return {
        "path": path,
        "content_type": "application/json",
        "content": json.dumps(content, indent=2, sort_keys=True),
    }


def _build_description(
    *,
    topic: str,
    source_package_path: str,
    monetization_risk_report_path: str,
    source_attribution_path: str,
) -> str:
    return "\n".join(
        [
            topic,
            "",
            "Review note: This YouTube Shorts export pack is generated for manual review only.",
            "Verify script facts, source attribution, asset rights, originality, and P29 editorial approval before any manual upload.",
            "",
            f"Source package: {source_package_path}",
            f"Risk report: {monetization_risk_report_path}",
            f"Source attribution: {source_attribution_path}",
        ]
    )


def _build_first_frame_notes(first_frame_option: dict[str, Any]) -> str:
    risk_notes = "\n".join(f"- {note}" for note in first_frame_option["risk_notes"])
    return "\n".join(
        [
            f"Selected concept: {first_frame_option['concept_id']}",
            f"Visual pattern: {first_frame_option['visual_pattern']}",
            f"Suggested on-frame text: {first_frame_option['suggested_text']}",
            f"Layout: {first_frame_option['visual_layout']}",
            f"Emotion: {first_frame_option['emotion']}",
            f"Contrast idea: {first_frame_option['contrast_idea']}",
            "",
            "Review notes:",
            risk_notes,
        ]
    )


def _build_risk_note(
    *,
    decision_state: str,
    blocking_reasons: list[str],
    required_actions: list[str],
) -> str:
    reason_lines = "\n".join(f"- {reason}" for reason in blocking_reasons)
    action_lines = "\n".join(f"- {action}" for action in required_actions)
    return "\n".join(
        [
            "YouTube Shorts export risk note",
            "publish_allowed: false",
            "review_required: true",
            f"P26 decision state: {decision_state}",
            "P29 editorial status: missing",
            "",
            "Blocking reasons:",
            reason_lines,
            "",
            "Required actions:",
            action_lines,
            "",
            "This export pack is not an upload instruction, rights clearance, monetization approval, or publish approval.",
        ]
    )


def _build_rights_note(
    *,
    source_attribution_path: str,
    monetization_risk_report_path: str,
) -> str:
    return "\n".join(
        [
            "Rights note",
            "No automatic rights clearance is granted by this export pack.",
            "Review all footage, images, music, voiceover, logo, and source attribution before any manual upload.",
            f"Source attribution path: {source_attribution_path}",
            f"Monetization risk report path: {monetization_risk_report_path}",
            "P26 review and P29 editorial approval remain required.",
        ]
    )


def build_youtube_shorts_export_pack(
    topic: str,
    *,
    subject: str | None = None,
    package_id: str = "pkg-youtube-shorts-export-example",
    video_asset_path: str = "renders/shorts/neymar-2014-comeback-pressure.mp4",
    source_package_path: str = "content_package.json",
    monetization_risk_report_path: str = "monetization_risk_report.json",
    source_attribution_path: str = "source_attribution.json",
    hashtags: tuple[str, ...] | list[str] | None = None,
    publish_block_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, review-only YouTube Shorts export pack.

    The returned structure represents file contents and metadata that an
    operator can review before manually preparing a Short. It intentionally
    keeps ``publish_allowed`` false and does not write files, render assets,
    call platform APIs, or approve publication.
    """

    topic_text = _clean(topic, "topic")
    subject_text = _clean(subject or topic_text, "subject")
    package_id_text = _clean(package_id, "package_id")
    video_path_text = _clean(video_asset_path, "video_asset_path")
    source_package_text = _clean(source_package_path, "source_package_path")
    risk_report_text = _clean(monetization_risk_report_path, "monetization_risk_report_path")
    attribution_text = _clean(source_attribution_path, "source_attribution_path")

    title_option = build_title_options(topic_text, subject=subject_text, content_type="short")[0]
    first_frame_option = build_visual_concepts(topic_text, subject=subject_text, content_type="short")[
        "first_frame_options"
    ][0]
    cta_option = build_cta_options(topic_text, subject=subject_text, content_type="short")[0]

    decision = publish_block_decision or {}
    decision_state = str(decision.get("decision_state") or "review_required")
    blocking_reasons = _list_or_default(decision.get("blocking_reasons"), DEFAULT_BLOCKING_REASONS)
    required_actions = _list_or_default(decision.get("required_actions"), DEFAULT_REQUIRED_ACTIONS)
    hashtag_lines = list(hashtags or DEFAULT_YOUTUBE_SHORTS_HASHTAGS)

    metadata = {
        "schema_version": "p27.youtube_shorts_export_pack.v1",
        "package_id": package_id_text,
        "platform": YOUTUBE_SHORTS_PLATFORM,
        "export_directory": YOUTUBE_SHORTS_EXPORT_DIRECTORY,
        "content_type": "short",
        "video_asset_path": video_path_text,
        "copy_asset_paths": {
            "title": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}title.txt",
            "description": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}description.txt",
            "hashtags": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}hashtags.txt",
            "pinned_comment": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}pinned_comment.txt",
            "first_frame_notes": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}first_frame_notes.txt",
            "risk_note": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}risk_note.txt",
            "rights_note": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}rights_note.txt",
        },
        "rights_note_path": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}rights_note.txt",
        "review_status_path": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}review_status.json",
        "source_package_path": source_package_text,
        "monetization_risk_report_path": risk_report_text,
        "source_attribution_path": attribution_text,
        "publish_allowed": False,
        "review_required": True,
        "blocking_reasons": blocking_reasons,
        "required_actions": required_actions,
        "created_by_step": "P27-02",
        "planned_epic": "P27",
        "p25_packaging_sources": {
            "title_option_id": title_option["option_id"],
            "first_frame_concept_id": first_frame_option["concept_id"],
            "cta_id": cta_option["cta_id"],
        },
        "p26_decision_state": decision_state,
    }

    review_status = {
        "platform": YOUTUBE_SHORTS_PLATFORM,
        "package_id": package_id_text,
        "export_status": "blocked_until_review",
        "publish_allowed": False,
        "p26_review_status": "required",
        "p29_editorial_status": "missing",
        "rights_status": "review_required",
        "monetization_status": "review_required",
        "source_attribution_status": "review_required",
        "music_license_status": "review_required",
        "originality_status": "review_required",
        "blocking_reasons": blocking_reasons,
        "required_actions": required_actions,
        "reviewer_role": "publishing operator",
        "notes": [
            "Generated YouTube Shorts export pack is review-only.",
            "P26 rights and monetization review remain required.",
            "P29 editorial approval remains required before any publish-ready state.",
        ],
    }

    description = _build_description(
        topic=topic_text,
        source_package_path=source_package_text,
        monetization_risk_report_path=risk_report_text,
        source_attribution_path=attribution_text,
    )
    first_frame_notes = _build_first_frame_notes(first_frame_option)
    risk_note = _build_risk_note(
        decision_state=decision_state,
        blocking_reasons=blocking_reasons,
        required_actions=required_actions,
    )
    rights_note = _build_rights_note(
        source_attribution_path=attribution_text,
        monetization_risk_report_path=risk_report_text,
    )

    files: dict[str, dict[str, Any]] = {
        "video.mp4": {
            "path": f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}video.mp4",
            "content_type": "video/mp4",
            "source_asset_path": video_path_text,
            "status": "reference_only_not_committed",
        },
        "title.txt": _text_file(f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}title.txt", title_option["title_text"]),
        "description.txt": _text_file(f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}description.txt", description),
        "hashtags.txt": _text_file(f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}hashtags.txt", "\n".join(hashtag_lines)),
        "pinned_comment.txt": _text_file(
            f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}pinned_comment.txt",
            cta_option["cta_text"],
        ),
        "first_frame_notes.txt": _text_file(
            f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}first_frame_notes.txt",
            first_frame_notes,
        ),
        "risk_note.txt": _text_file(f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}risk_note.txt", risk_note),
        "rights_note.txt": _text_file(f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}rights_note.txt", rights_note),
        "metadata.json": _json_file(f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}metadata.json", metadata),
        "review_status.json": _json_file(f"{YOUTUBE_SHORTS_EXPORT_DIRECTORY}review_status.json", review_status),
    }

    return {
        "schema_version": "p27.youtube_shorts_export_pack.v1",
        "package_id": package_id_text,
        "platform": YOUTUBE_SHORTS_PLATFORM,
        "export_directory": YOUTUBE_SHORTS_EXPORT_DIRECTORY,
        "required_files": list(YOUTUBE_SHORTS_REQUIRED_FILES),
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
            "title_option": title_option,
            "first_frame_option": first_frame_option,
            "cta_option": cta_option,
        },
        "metadata": metadata,
        "review_status": review_status,
        "files": files,
    }
