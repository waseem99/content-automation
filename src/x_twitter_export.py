"""Deterministic X/Twitter export pack helpers.

The helpers in this module build a review-only X/Twitter post and optional
thread manifest. They do not post through the X API, scrape replies, collect
engagement data, approve rights, or mark anything publish-ready.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from src.cta_library import build_cta_options

X_TWITTER_PLATFORM = "x_twitter"
X_TWITTER_EXPORT_DIRECTORY = "exports/x_twitter/"

X_TWITTER_REQUIRED_FILES = (
    "video.mp4",
    "post.txt",
    "thread.txt",
    "hashtags.txt",
    "debate_prompt.txt",
    "risk_note.txt",
    "metadata.json",
    "review_status.json",
)

ContentType = Literal["short", "explainer"]

DEFAULT_HASHTAGS = ("#football", "#soccer", "#footballtalk")
DEFAULT_BLOCKING_REASONS = (
    "Factual/stat review required.",
    "P26 rights and monetization review required.",
    "P29 editorial approval required.",
)
DEFAULT_REQUIRED_ACTIONS = (
    "Verify all stats, dates, player claims, and source references.",
    "Review footage, image, logo, and music rights before any manual post.",
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


def _build_post(*, subject: str, cta_text: str) -> str:
    post = f"{subject} is still a football debate, not a settled story. {cta_text}"
    if len(post) > 280:
        return post[:277].rstrip() + "..."
    return post


def _build_thread(*, topic: str, subject: str, content_type: ContentType) -> str:
    if content_type == "explainer":
        points = [
            f"1/ {topic}",
            f"2/ The key angle is why {subject} still creates debate among fans.",
            "3/ Any stats, footage, music, and source claims need review before posting.",
            "4/ Final question: what changes your view on this football story?",
        ]
    else:
        points = [
            f"1/ Short context: {topic}",
            f"2/ The debate is about pressure, timing, and fan memory around {subject}.",
            "3/ Check sources, rights, and originality before turning this into a public post.",
        ]
    return "\n".join(points)


def _build_risk_note(*, decision_state: str, blocking_reasons: list[str], required_actions: list[str]) -> str:
    reason_lines = "\n".join(f"- {reason}" for reason in blocking_reasons)
    action_lines = "\n".join(f"- {action}" for action in required_actions)
    return "\n".join(
        [
            "X/Twitter export risk note",
            "publish_allowed: false",
            "review_required: true",
            f"P26 decision state: {decision_state}",
            "P29 editorial status: missing",
            "Stats, rights, and source claims are not automatically cleared.",
            "",
            "Blocking reasons:",
            reason_lines,
            "",
            "Required actions:",
            action_lines,
            "",
            "This export pack is not an X API post, reply scrape, engagement scrape, rights clearance, monetization approval, or publish approval.",
        ]
    )


def build_x_twitter_export_pack(
    topic: str,
    *,
    subject: str | None = None,
    content_type: ContentType = "short",
    package_id: str = "pkg-x-twitter-export-example",
    video_asset_path: str = "renders/shorts/neymar-2014-comeback-pressure.mp4",
    source_package_path: str = "content_package.json",
    monetization_risk_report_path: str = "monetization_risk_report.json",
    source_attribution_path: str = "source_attribution.json",
    hashtags: tuple[str, ...] | list[str] | None = None,
    publish_block_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, review-only X/Twitter export pack."""

    if content_type not in {"short", "explainer"}:
        raise ValueError("content_type must be 'short' or 'explainer'")

    topic_text = _clean(topic, "topic")
    subject_text = _clean(subject or topic_text, "subject")
    package_id_text = _clean(package_id, "package_id")
    video_path_text = _clean(video_asset_path, "video_asset_path")
    source_package_text = _clean(source_package_path, "source_package_path")
    risk_report_text = _clean(monetization_risk_report_path, "monetization_risk_report_path")
    attribution_text = _clean(source_attribution_path, "source_attribution_path")

    cta_option = build_cta_options(topic_text, subject=subject_text, content_type=content_type)[0]
    decision = publish_block_decision or {}
    decision_state = str(decision.get("decision_state") or "review_required")
    blocking_reasons = _list_or_default(decision.get("blocking_reasons"), DEFAULT_BLOCKING_REASONS)
    required_actions = _list_or_default(decision.get("required_actions"), DEFAULT_REQUIRED_ACTIONS)
    hashtag_lines = list(hashtags or DEFAULT_HASHTAGS)

    metadata = {
        "schema_version": "p27.x_twitter_export_pack.v1",
        "package_id": package_id_text,
        "platform": X_TWITTER_PLATFORM,
        "export_directory": X_TWITTER_EXPORT_DIRECTORY,
        "content_type": content_type,
        "video_asset_path": video_path_text,
        "copy_asset_paths": {
            "post": f"{X_TWITTER_EXPORT_DIRECTORY}post.txt",
            "thread": f"{X_TWITTER_EXPORT_DIRECTORY}thread.txt",
            "hashtags": f"{X_TWITTER_EXPORT_DIRECTORY}hashtags.txt",
            "debate_prompt": f"{X_TWITTER_EXPORT_DIRECTORY}debate_prompt.txt",
            "risk_note": f"{X_TWITTER_EXPORT_DIRECTORY}risk_note.txt",
        },
        "review_status_path": f"{X_TWITTER_EXPORT_DIRECTORY}review_status.json",
        "source_package_path": source_package_text,
        "monetization_risk_report_path": risk_report_text,
        "source_attribution_path": attribution_text,
        "publish_allowed": False,
        "review_required": True,
        "blocking_reasons": blocking_reasons,
        "required_actions": required_actions,
        "created_by_step": "P27-04",
        "planned_epic": "P27",
        "copy_constraints": {
            "post_max_chars": 280,
            "thread_required_for": ["explainer"],
            "style": "short_specific_debate_oriented",
        },
        "p25_packaging_sources": {"cta_id": cta_option["cta_id"]},
        "p26_decision_state": decision_state,
    }

    review_status = {
        "platform": X_TWITTER_PLATFORM,
        "package_id": package_id_text,
        "export_status": "blocked_until_review",
        "publish_allowed": False,
        "p26_review_status": "required",
        "p29_editorial_status": "missing",
        "rights_status": "review_required",
        "monetization_status": "review_required",
        "source_attribution_status": "review_required",
        "factual_status": "review_required",
        "originality_status": "review_required",
        "blocking_reasons": blocking_reasons,
        "required_actions": required_actions,
        "reviewer_role": "publishing operator",
        "notes": [
            "X/Twitter export pack is review-only.",
            "Stats and source claims need human verification.",
            "P29 editorial approval remains required before any publish-ready state.",
        ],
    }

    post = _build_post(subject=subject_text, cta_text=cta_option["cta_text"])
    thread = _build_thread(topic=topic_text, subject=subject_text, content_type=content_type)
    risk_note = _build_risk_note(
        decision_state=decision_state,
        blocking_reasons=blocking_reasons,
        required_actions=required_actions,
    )

    files: dict[str, dict[str, Any]] = {
        "video.mp4": {
            "path": f"{X_TWITTER_EXPORT_DIRECTORY}video.mp4",
            "content_type": "video/mp4",
            "source_asset_path": video_path_text,
            "status": "reference_only_not_committed",
        },
        "post.txt": _text_file(f"{X_TWITTER_EXPORT_DIRECTORY}post.txt", post),
        "thread.txt": _text_file(f"{X_TWITTER_EXPORT_DIRECTORY}thread.txt", thread),
        "hashtags.txt": _text_file(f"{X_TWITTER_EXPORT_DIRECTORY}hashtags.txt", "\n".join(hashtag_lines)),
        "debate_prompt.txt": _text_file(f"{X_TWITTER_EXPORT_DIRECTORY}debate_prompt.txt", cta_option["cta_text"]),
        "risk_note.txt": _text_file(f"{X_TWITTER_EXPORT_DIRECTORY}risk_note.txt", risk_note),
        "metadata.json": _json_file(f"{X_TWITTER_EXPORT_DIRECTORY}metadata.json", metadata),
        "review_status.json": _json_file(f"{X_TWITTER_EXPORT_DIRECTORY}review_status.json", review_status),
    }

    return {
        "schema_version": "p27.x_twitter_export_pack.v1",
        "package_id": package_id_text,
        "platform": X_TWITTER_PLATFORM,
        "export_directory": X_TWITTER_EXPORT_DIRECTORY,
        "required_files": list(X_TWITTER_REQUIRED_FILES),
        "publish_allowed": False,
        "review_required": True,
        "source_inputs": {
            "topic": topic_text,
            "subject": subject_text,
            "source_package_path": source_package_text,
            "monetization_risk_report_path": risk_report_text,
            "source_attribution_path": attribution_text,
        },
        "selected_p25_fields": {"cta_option": cta_option},
        "metadata": metadata,
        "review_status": review_status,
        "files": files,
    }
