"""Shorts-to-long-form funnel and cutdown map helpers for P28.

These helpers define how Shorts, explainers, and long-form videos connect as a
review-only channel funnel. They do not render cutdowns, select clips from
analytics, upload to platforms, scrape engagement, or bypass review gates.
"""

from __future__ import annotations

from typing import Any

from src.topic_calendar import RECOMMENDATION_STATES

FUNNEL_SCHEMA_VERSION = "p28.shorts_longform_funnel.v1"
FUNNEL_VALIDATION_SCHEMA_VERSION = "p28.shorts_longform_funnel_validation.v1"

FUNNEL_TYPES = (
    "short_teaser_to_long_form",
    "long_form_to_shorts_cutdowns",
    "explainer_to_debate_short",
    "series_episode_to_next_episode_tease",
)

CUTDOWN_MAP_FIELDS = (
    "source_video",
    "hook_clip",
    "cutdown_angle",
    "target_platform",
    "cta",
    "linked_long_form_episode",
)

REQUIRED_CUTDOWN_ENTRY_FIELDS = (
    "map_id",
    "format_example",
    "funnel_type",
    "source_video",
    "hook_clip",
    "cutdown_angle",
    "target_platform",
    "cta",
    "linked_long_form_episode",
    "related_episode_fields",
    "series",
    "review_status",
    "publish_allowed",
    "review_required",
)

TARGET_PLATFORMS = (
    "youtube_shorts",
    "tiktok",
    "instagram_reels",
    "facebook_reels",
    "x_twitter",
    "youtube_long_form",
)

FORMAT_EXAMPLES = (
    "football_player_legacy",
    "world_cup_hype",
    "match_moment_format",
)


def _entry(
    *,
    map_id: str,
    format_example: str,
    funnel_type: str,
    source_video: str,
    hook_clip: str,
    cutdown_angle: str,
    target_platform: str,
    cta: str,
    linked_long_form_episode: str,
    series: str,
) -> dict[str, Any]:
    return {
        "map_id": map_id,
        "format_example": format_example,
        "funnel_type": funnel_type,
        "source_video": source_video,
        "hook_clip": hook_clip,
        "cutdown_angle": cutdown_angle,
        "target_platform": target_platform,
        "cta": cta,
        "linked_long_form_episode": linked_long_form_episode,
        "related_episode_fields": {
            "episode_id": linked_long_form_episode,
            "source_chapter": "cold_open" if funnel_type == "short_teaser_to_long_form" else "turning_point",
            "content_package_path": "content_package.json",
            "longform_plan_path": "outputs/longform/pkg-p28-longform-neymar-2014/longform_plan.json",
        },
        "series": series,
        "review_status": "needs_review_before_export",
        "publish_allowed": False,
        "review_required": True,
    }


def build_shorts_longform_funnel_contract() -> dict[str, Any]:
    """Build a deterministic review-only funnel and cutdown map contract."""

    cutdown_map = [
        _entry(
            map_id="cutdown-player-legacy-teaser",
            format_example="football_player_legacy",
            funnel_type="short_teaser_to_long_form",
            source_video="outputs/longform/pkg-p28-longform-neymar-2014/final_video_placeholder.txt",
            hook_clip="Opening pressure question: was Neymar carrying Brazil's entire 2014 dream?",
            cutdown_angle="Use a sharp legacy-pressure question to push viewers to the full long-form breakdown.",
            target_platform="youtube_shorts",
            cta="Watch the full pressure breakdown on the channel.",
            linked_long_form_episode="episode-neymar-2014-pressure",
            series="Football Pressure Index",
        ),
        _entry(
            map_id="cutdown-player-legacy-payoff",
            format_example="football_player_legacy",
            funnel_type="long_form_to_shorts_cutdowns",
            source_video="outputs/longform/pkg-p28-longform-neymar-2014/final_video_placeholder.txt",
            hook_clip="Legacy payoff section explaining why the injury changed how the tournament is remembered.",
            cutdown_angle="Turn the long-form payoff into a standalone Shorts debate about legacy and pressure.",
            target_platform="instagram_reels",
            cta="Comment if this changed Neymar's legacy or only Brazil's story.",
            linked_long_form_episode="episode-neymar-2014-pressure",
            series="Football Pressure Index",
        ),
        _entry(
            map_id="cutdown-world-cup-hype-teaser",
            format_example="world_cup_hype",
            funnel_type="explainer_to_debate_short",
            source_video="outputs/longform/pkg-p28-world-cup-what-if-2010/final_video_placeholder.txt",
            hook_clip="What if Ghana scored the 2010 World Cup penalty?",
            cutdown_angle="Frame a speculative World Cup question while clearly pointing viewers to the sourced explainer.",
            target_platform="tiktok",
            cta="Watch the full what-if breakdown before choosing a side.",
            linked_long_form_episode="episode-ghana-2010-what-if",
            series="World Cup What Ifs",
        ),
        _entry(
            map_id="cutdown-match-moment-next-episode",
            format_example="match_moment_format",
            funnel_type="series_episode_to_next_episode_tease",
            source_video="outputs/longform/pkg-p28-moment-that-changed/final_video_placeholder.txt",
            hook_clip="One match moment changed everything, but the next episode tests an even bigger turning point.",
            cutdown_angle="Use the end-card tease to move viewers from one series episode into the next planned story.",
            target_platform="x_twitter",
            cta="Reply with the next match moment we should break down.",
            linked_long_form_episode="episode-moment-that-changed-next",
            series="The Moment That Changed",
        ),
    ]

    return {
        "schema_version": FUNNEL_SCHEMA_VERSION,
        "parent_epic": 330,
        "content_type": "shorts_longform_funnel_contract",
        "funnel_types": [
            {
                "type": "short_teaser_to_long_form",
                "description": "A Short opens a strong curiosity gap and routes viewers to the related long-form episode.",
            },
            {
                "type": "long_form_to_shorts_cutdowns",
                "description": "A reviewed long-form video produces rights-safe Shorts candidates after editorial review.",
            },
            {
                "type": "explainer_to_debate_short",
                "description": "A factual explainer becomes a focused debate Short without losing source caveats.",
            },
            {
                "type": "series_episode_to_next_episode_tease",
                "description": "A series episode end-card becomes a next-episode tease and comment prompt.",
            },
        ],
        "cutdown_map_fields": list(CUTDOWN_MAP_FIELDS),
        "cutdown_map": cutdown_map,
        "platform_connections": {
            "p27_export_pack_after_review": True,
            "youtube_long_form_packaging_after_review": True,
            "target_platforms": list(TARGET_PLATFORMS),
            "automatic_upload_out_of_scope": True,
            "automatic_rendering_out_of_scope": True,
            "analytics_based_selection_out_of_scope": True,
        },
        "planning_connections": {
            "topic_calendar_path": "docs/operations/p28-topic-calendar-example.json",
            "series_metadata_path": "docs/operations/p28-series-metadata-example.json",
            "produce_longform_contract_path": "docs/operations/p28-produce-longform-output-contract-example.json",
            "content_package_path": "content_package.json",
        },
        "recommendation_states": list(RECOMMENDATION_STATES),
        "risk_fields": {
            "rights_review_required": True,
            "factual_review_required": True,
            "source_attribution_required": True,
            "editorial_review_required": True,
            "publish_allowed": False,
            "review_required": True,
        },
        "publish_allowed": False,
        "review_required": True,
    }


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_shorts_longform_funnel_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the P28 funnel/cutdown map contract."""

    errors: list[str] = []

    _require(contract.get("schema_version") == FUNNEL_SCHEMA_VERSION, errors, "schema_version mismatch")
    _require(contract.get("parent_epic") == 330, errors, "parent epic must be 330")
    _require(contract.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(contract.get("review_required") is True, errors, "review_required must remain true")

    funnel_types = contract.get("funnel_types", [])
    funnel_type_names = [item.get("type") for item in funnel_types if isinstance(item, dict)]
    _require(set(FUNNEL_TYPES) <= set(funnel_type_names), errors, "missing required funnel types")
    _require(set(CUTDOWN_MAP_FIELDS) <= set(contract.get("cutdown_map_fields", [])), errors, "missing cutdown map fields")

    cutdown_map = contract.get("cutdown_map", [])
    _require(isinstance(cutdown_map, list) and bool(cutdown_map), errors, "cutdown_map must be a non-empty list")
    seen_format_examples: list[str] = []
    for entry in cutdown_map if isinstance(cutdown_map, list) else []:
        _require(isinstance(entry, dict), errors, "cutdown entry must be an object")
        if not isinstance(entry, dict):
            continue
        _require(set(REQUIRED_CUTDOWN_ENTRY_FIELDS) <= set(entry), errors, "cutdown entry missing required fields")
        for field in CUTDOWN_MAP_FIELDS:
            value = entry.get(field)
            _require(isinstance(value, str) and bool(value.strip()), errors, f"{field} must be non-empty text")
        _require(entry.get("funnel_type") in FUNNEL_TYPES, errors, "invalid funnel_type")
        _require(entry.get("target_platform") in TARGET_PLATFORMS, errors, "invalid target_platform")
        if isinstance(entry.get("format_example"), str):
            seen_format_examples.append(entry["format_example"])
        _require(entry.get("publish_allowed") is False, errors, "cutdown publish_allowed must remain false")
        _require(entry.get("review_required") is True, errors, "cutdown review_required must remain true")
        _require(entry.get("review_status") == "needs_review_before_export", errors, "cutdown review_status must require review before export")
        related_episode_fields = entry.get("related_episode_fields", {})
        _require(isinstance(related_episode_fields, dict), errors, "related_episode_fields must be an object")
        if isinstance(related_episode_fields, dict):
            _require(bool(related_episode_fields.get("episode_id")), errors, "related episode_id required")
            _require(related_episode_fields.get("content_package_path") == "content_package.json", errors, "content package link required")
            _require(bool(related_episode_fields.get("longform_plan_path")), errors, "longform plan link required")

    _require(set(FORMAT_EXAMPLES) <= set(seen_format_examples), errors, "required format examples missing")

    platform_connections = contract.get("platform_connections", {})
    if not isinstance(platform_connections, dict):
        platform_connections = {}
    _require(platform_connections.get("p27_export_pack_after_review") is True, errors, "P27 export after review required")
    _require(platform_connections.get("youtube_long_form_packaging_after_review") is True, errors, "YouTube long-form packaging after review required")
    _require(set(TARGET_PLATFORMS) <= set(platform_connections.get("target_platforms", [])), errors, "target platforms missing")
    _require(platform_connections.get("automatic_upload_out_of_scope") is True, errors, "automatic upload must be out of scope")
    _require(platform_connections.get("automatic_rendering_out_of_scope") is True, errors, "automatic rendering must be out of scope")
    _require(platform_connections.get("analytics_based_selection_out_of_scope") is True, errors, "analytics-based selection must be out of scope")

    planning_connections = contract.get("planning_connections", {})
    if not isinstance(planning_connections, dict):
        planning_connections = {}
    _require(planning_connections.get("topic_calendar_path") == "docs/operations/p28-topic-calendar-example.json", errors, "topic calendar connection required")
    _require(planning_connections.get("series_metadata_path") == "docs/operations/p28-series-metadata-example.json", errors, "series metadata connection required")
    _require(planning_connections.get("produce_longform_contract_path") == "docs/operations/p28-produce-longform-output-contract-example.json", errors, "produce-longform connection required")
    _require(planning_connections.get("content_package_path") == "content_package.json", errors, "content package connection required")

    risk_fields = contract.get("risk_fields", {})
    if not isinstance(risk_fields, dict):
        risk_fields = {}
    _require(risk_fields.get("rights_review_required") is True, errors, "rights review must be required")
    _require(risk_fields.get("factual_review_required") is True, errors, "factual review must be required")
    _require(risk_fields.get("source_attribution_required") is True, errors, "source attribution must be required")
    _require(risk_fields.get("editorial_review_required") is True, errors, "editorial review must be required")
    _require(risk_fields.get("publish_allowed") is False, errors, "risk publish_allowed must remain false")
    _require(risk_fields.get("review_required") is True, errors, "risk review_required must remain true")

    return {
        "schema_version": FUNNEL_VALIDATION_SCHEMA_VERSION,
        "is_valid": not errors,
        "funnel_types_checked": list(FUNNEL_TYPES),
        "cutdown_map_fields_checked": list(CUTDOWN_MAP_FIELDS),
        "format_examples_checked": list(FORMAT_EXAMPLES),
        "cutdown_entry_count": len(cutdown_map) if isinstance(cutdown_map, list) else 0,
        "publish_allowed": False,
        "review_required": True,
        "errors": errors,
    }
