"""P48 platform-specific creative template engine.

This module makes local output platform-native. It converts a raw brief or prior
pipeline/export package into tailored creative templates for YouTube Shorts,
Instagram Reels, TikTok, longform YouTube, and carousel/newsletter reuse.

It does not scrape trends, call platform APIs, render/edit video, upload,
publish, or guarantee performance.
"""

from __future__ import annotations

import json
from typing import Any

from src.p45_video_pipeline_orchestrator import run_video_content_pipeline

P48_TEMPLATE_VERSION = "p48.platform_template_pack.v1"
TARGET_PLATFORMS = ("youtube_shorts", "instagram_reels", "tiktok", "youtube_long", "carousel_newsletter")

PLATFORM_RULES: dict[str, dict[str, Any]] = {
    "youtube_shorts": {
        "format": "vertical_short",
        "duration": "35-60s",
        "hook_style": "Clear contradiction or mistake in the first 1-2 seconds.",
        "pacing_rules": ["No intro", "Cut every 2-4 seconds", "Deliver one clear payoff"],
        "caption_style": "Bold mobile captions with 1-3 emphasized words per line.",
        "scene_count": "5-7 scenes",
        "cta_style": "Save/subscribe CTA after payoff.",
        "metadata_guidance": "Search-friendly title plus practical description and 3-5 hashtags.",
        "export_notes": "9:16, caption-safe margins, strong cover frame.",
    },
    "instagram_reels": {
        "format": "vertical_short",
        "duration": "20-45s",
        "hook_style": "Visual-first hook with relatable problem or before/after contrast.",
        "pacing_rules": ["Use quick visual rhythm", "Lean into aesthetic clarity", "End with share/save cue"],
        "caption_style": "Short caption overlays; avoid crowding the frame.",
        "scene_count": "4-6 scenes",
        "cta_style": "Share/save CTA; soft comment prompt.",
        "metadata_guidance": "Caption should read naturally with niche hashtags.",
        "export_notes": "9:16, clean cover, avoid text near UI edges.",
    },
    "tiktok": {
        "format": "vertical_short",
        "duration": "15-40s",
        "hook_style": "Conversational cold open that feels native and direct.",
        "pacing_rules": ["Start mid-thought", "Use fast pattern interrupts", "Keep payoff simple"],
        "caption_style": "Casual captions; emphasize surprise or mistake wording.",
        "scene_count": "4-6 scenes",
        "cta_style": "Comment prompt or template request.",
        "metadata_guidance": "Plain-language caption; avoid over-polished copy.",
        "export_notes": "9:16, raw/native feel, fast first frame.",
    },
    "youtube_long": {
        "format": "longform",
        "duration": "6-10 min expansion",
        "hook_style": "Promise the full framework and show the cost of the wrong approach.",
        "pacing_rules": ["Open loop in first 15 seconds", "Use chaptered structure", "Add proof/examples every 60-90 seconds"],
        "caption_style": "Optional captions; use lower-thirds for key terms.",
        "scene_count": "6-9 chapters",
        "cta_style": "Subscribe/download CTA after value delivery.",
        "metadata_guidance": "SEO title, detailed description, chapters, and resource links.",
        "export_notes": "16:9 or talking-head/screen-share format; retain source evidence.",
    },
    "carousel_newsletter": {
        "format": "static_reuse",
        "duration": "7-10 slides or 500-900 words",
        "hook_style": "Slide/email headline built around mistake, checklist, or framework.",
        "pacing_rules": ["One idea per slide/section", "Use checklist flow", "End with practical action"],
        "caption_style": "Short slide copy; newsletter can expand each point.",
        "scene_count": "7-10 slides/sections",
        "cta_style": "Download/checklist/reply CTA.",
        "metadata_guidance": "Use a saveable title and concise summary.",
        "export_notes": "Readable text, strong hierarchy, no copyrighted visuals.",
    },
}


def normalize_template_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw brief, P45 package, P46 export pack, or P47 runner result."""

    pipeline = _extract_pipeline(payload)
    if not pipeline.get("is_valid"):
        return {"is_valid": False, "validation_errors": pipeline.get("validation_errors", ["invalid_payload"])}
    video = pipeline.get("video_package", {})
    brief = video.get("brief", {}) if isinstance(video.get("brief"), dict) else {}
    metadata = pipeline.get("monetization_report", {}).get("metadata_pack", {})
    production = pipeline.get("production_pack", {})
    fields = {
        "topic": brief.get("topic") or payload.get("topic") or "video topic",
        "audience": brief.get("audience") or payload.get("audience") or "target audience",
        "primary_platform": brief.get("platform") or payload.get("platform") or "youtube_shorts",
        "title_options": video.get("title_options", []),
        "hook": video.get("hook", ""),
        "script": video.get("script", ""),
        "storyboard_frames": production.get("storyboard_frames", []),
        "metadata": metadata,
        "cta": metadata.get("primary_cta") or metadata.get("pinned_comment") or "Save this for later.",
        "pipeline_status": pipeline.get("pipeline_status"),
    }
    errors = []
    if not fields["hook"]:
        errors.append("missing_hook")
    if not fields["script"]:
        errors.append("missing_script")
    return {"is_valid": not errors, "validation_errors": errors, "fields": fields, "pipeline_package": pipeline}


def _extract_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") == "p45.end_to_end_video_pipeline.v1":
        return payload
    if payload.get("schema_version") == "p46.local_producer_export_pack.v1":
        return payload.get("pipeline_package", {})
    if payload.get("schema_version") == "p47.local_folder_runner.v1":
        return payload.get("export_pack", {}).get("pipeline_package", {}) or payload.get("pipeline_package", {})
    return run_video_content_pipeline(payload)


def build_platform_template_pack(payload: dict[str, Any], target_platforms: list[str] | None = None) -> dict[str, Any]:
    normalized = normalize_template_payload(payload)
    if not normalized.get("is_valid"):
        return {
            "schema_version": P48_TEMPLATE_VERSION,
            "is_valid": False,
            "validation_errors": normalized.get("validation_errors", []),
            **_guardrails(),
        }
    fields = normalized["fields"]
    platforms = _select_platforms(target_platforms)
    templates = {platform: build_platform_template(platform, fields) for platform in platforms}
    return {
        "schema_version": P48_TEMPLATE_VERSION,
        "is_valid": True,
        "primary_platform": fields["primary_platform"],
        "recommended_primary_platform": recommend_primary_platform(fields, templates),
        "templates": templates,
        "reuse_plan": build_reuse_plan(templates),
        "platform_templates_json_ready": True,
        **_guardrails(),
    }


def _select_platforms(target_platforms: list[str] | None) -> list[str]:
    if not target_platforms:
        return list(TARGET_PLATFORMS)
    selected = [platform for platform in target_platforms if platform in PLATFORM_RULES]
    return selected or list(TARGET_PLATFORMS)


def build_platform_template(platform: str, fields: dict[str, Any]) -> dict[str, Any]:
    rules = PLATFORM_RULES[platform]
    title = adapt_title(platform, fields)
    hook = adapt_hook(platform, fields)
    cta = adapt_cta(platform, fields)
    return {
        "platform": platform,
        "format": rules["format"],
        "recommended_duration": rules["duration"],
        "title": title,
        "adapted_hook": hook,
        "adapted_cta": cta,
        "hook_style": rules["hook_style"],
        "pacing_rules": rules["pacing_rules"],
        "caption_style": rules["caption_style"],
        "scene_count_guidance": rules["scene_count"],
        "metadata_guidance": rules["metadata_guidance"],
        "storyboard_adaptation_notes": adapt_storyboard_notes(platform, fields),
        "export_notes": rules["export_notes"],
        "risk_compliance_notes": [
            "Use owned/licensed assets only.",
            "Do not use celebrity likeness, unlicensed music, or third-party clips.",
            "Run human review before publishing.",
        ],
        "performance_guaranteed": False,
    }


def adapt_title(platform: str, fields: dict[str, Any]) -> str:
    topic = fields["topic"]
    existing = fields["title_options"][0] if fields["title_options"] else f"Fix {topic}"
    if platform == "tiktok":
        return f"Nobody tells you this about {topic}"
    if platform == "instagram_reels":
        return f"Before you try {topic}, watch this"
    if platform == "youtube_long":
        return f"The complete {topic} framework explained"
    if platform == "carousel_newsletter":
        return f"{topic}: the practical checklist"
    return existing


def adapt_hook(platform: str, fields: dict[str, Any]) -> str:
    topic = fields["topic"]
    audience = fields["audience"]
    base = fields["hook"]
    if platform == "tiktok":
        return f"You are probably doing {topic} the hard way."
    if platform == "instagram_reels":
        return f"Before you spend more time on {topic}, fix this first."
    if platform == "youtube_long":
        return f"In this video, I will break down the full {topic} system most {audience} miss."
    if platform == "carousel_newsletter":
        return f"Most {audience} miss these {topic} steps."
    return base


def adapt_cta(platform: str, fields: dict[str, Any]) -> str:
    topic = fields["topic"]
    if platform == "tiktok":
        return f"Comment 'template' if you want the {topic} checklist."
    if platform == "instagram_reels":
        return f"Save this and share it with someone working on {topic}."
    if platform == "youtube_long":
        return f"Subscribe and download the {topic} checklist from the description."
    if platform == "carousel_newsletter":
        return f"Download the {topic} checklist and apply step one today."
    return fields["cta"]


def adapt_storyboard_notes(platform: str, fields: dict[str, Any]) -> list[str]:
    topic = fields["topic"]
    if platform in {"youtube_shorts", "instagram_reels", "tiktok"}:
        return [
            "Compress the idea into one fast visual sequence.",
            "Keep each scene focused on one visual message.",
            "Use the first frame as the hook, not an intro screen.",
        ]
    if platform == "youtube_long":
        return [
            f"Expand each short scene into a chapter about {topic}.",
            "Add examples, proof, and recap checkpoints.",
            "Use chapters and clear lower-thirds for navigation.",
        ]
    return [
        "Turn each storyboard frame into one slide or newsletter section.",
        "Use concise headings and checklist-style copy.",
        "Keep visuals original and rights-safe.",
    ]


def recommend_primary_platform(fields: dict[str, Any], templates: dict[str, Any]) -> str:
    primary = fields.get("primary_platform")
    if primary in templates:
        return primary
    return "youtube_shorts"


def build_reuse_plan(templates: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "platform": platform,
            "title": template["title"],
            "cta": template["adapted_cta"],
            "format": template["format"],
            "export_note": template["export_notes"],
        }
        for platform, template in templates.items()
    ]


def render_platform_templates_json(payload: dict[str, Any]) -> str:
    return json.dumps(build_platform_template_pack(payload), indent=2, sort_keys=True) + "\n"


def _guardrails() -> dict[str, Any]:
    return {
        "local_only": True,
        "trend_scraping_performed": False,
        "platform_api_called": False,
        "rendering_performed": False,
        "upload_or_publish_performed": False,
        "performance_guaranteed": False,
    }
