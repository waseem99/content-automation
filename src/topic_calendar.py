"""Topic scoring and content calendar contract helpers for P28.

These helpers define a deterministic planning contract for prioritizing football
content ideas before production. They do not scrape live trends, call search
volume APIs, schedule posts, publish content, render assets, or bypass review.
"""

from __future__ import annotations

from typing import Any

from src.series_metadata import REQUIRED_SERIES_NAMES

TOPIC_CALENDAR_SCHEMA_VERSION = "p28.topic_calendar_contract.v1"
TOPIC_CALENDAR_VALIDATION_SCHEMA_VERSION = "p28.topic_calendar_validation.v1"

SCORING_DIMENSIONS = (
    "timeliness",
    "search_demand",
    "emotional_intensity",
    "comment_potential",
    "series_fit",
    "monetization_fit",
    "rights_risk",
    "production_effort",
)

RECOMMENDATION_STATES = (
    "produce_now",
    "hold",
    "needs_research",
    "reject_high_risk",
)

CONTENT_CALENDAR_FIELDS = (
    "publish_window",
    "platform",
    "series",
    "priority",
    "dependencies",
    "review_status",
)

REQUIRED_TOPIC_FIELDS = (
    "topic_id",
    "title",
    "series",
    "scores",
    "recommendation_state",
    "priority_score",
    "rationale",
    "rights_notes",
    "research_notes",
    "publish_allowed",
    "review_required",
)


def _priority_score(scores: dict[str, int]) -> int:
    positive = (
        scores["timeliness"]
        + scores["search_demand"]
        + scores["emotional_intensity"]
        + scores["comment_potential"]
        + scores["series_fit"]
        + scores["monetization_fit"]
    )
    risk_penalty = scores["rights_risk"] + scores["production_effort"]
    return positive - risk_penalty


def _recommendation_state(scores: dict[str, int]) -> str:
    if scores["rights_risk"] >= 5 or scores["production_effort"] >= 5:
        return "reject_high_risk"
    if scores["search_demand"] <= 2 or scores["series_fit"] <= 2:
        return "needs_research"
    if _priority_score(scores) >= 18 and scores["rights_risk"] <= 3:
        return "produce_now"
    return "hold"


def _topic(
    topic_id: str,
    title: str,
    series: str,
    scores: dict[str, int],
    rationale: str,
    rights_notes: str,
    research_notes: str,
) -> dict[str, Any]:
    recommendation_state = _recommendation_state(scores)
    return {
        "topic_id": topic_id,
        "title": title,
        "series": series,
        "scores": scores,
        "recommendation_state": recommendation_state,
        "priority_score": _priority_score(scores),
        "rationale": rationale,
        "rights_notes": rights_notes,
        "research_notes": research_notes,
        "publish_allowed": False,
        "review_required": True,
    }


def build_topic_calendar_contract() -> dict[str, Any]:
    """Build a deterministic topic scoring and calendar contract."""

    scored_topics = [
        _topic(
            "topic-neymar-2014-pressure",
            "Neymar 2014 World Cup injury and comeback pressure",
            "Football Pressure Index",
            {
                "timeliness": 4,
                "search_demand": 4,
                "emotional_intensity": 5,
                "comment_potential": 5,
                "series_fit": 5,
                "monetization_fit": 4,
                "rights_risk": 3,
                "production_effort": 2,
            },
            "High emotional football story with strong debate and repeatable pressure framing.",
            "Use rights-reviewed visuals or recreated editorial graphics; avoid unlicensed match footage.",
            "Verify injury timeline, match context, and post-tournament comeback reporting before script lock.",
        ),
        _topic(
            "topic-messi-2022-pressure",
            "Messi 2022 World Cup pressure before the final",
            "Legacy vs Future",
            {
                "timeliness": 3,
                "search_demand": 5,
                "emotional_intensity": 5,
                "comment_potential": 5,
                "series_fit": 5,
                "monetization_fit": 5,
                "rights_risk": 3,
                "production_effort": 3,
            },
            "Evergreen legacy debate with high search interest and strong long-form storytelling fit.",
            "Archive visuals and match footage require rights review; recreated timelines are safer.",
            "Separate verified match facts from legacy interpretation and opinion framing.",
        ),
        _topic(
            "topic-world-cup-what-if-2010",
            "What if Ghana scored the 2010 World Cup penalty?",
            "World Cup What Ifs",
            {
                "timeliness": 2,
                "search_demand": 3,
                "emotional_intensity": 5,
                "comment_potential": 5,
                "series_fit": 5,
                "monetization_fit": 3,
                "rights_risk": 4,
                "production_effort": 4,
            },
            "Excellent debate format, but needs careful sourcing and speculation guardrails.",
            "High rights sensitivity around match footage; prefer recreated diagrams and licensed stills.",
            "Needs extra research to separate factual sequence from counterfactual analysis.",
        ),
        _topic(
            "topic-transfer-rumor-live",
            "Unverified summer transfer rumor reaction",
            "The Moment That Changed",
            {
                "timeliness": 5,
                "search_demand": 2,
                "emotional_intensity": 3,
                "comment_potential": 4,
                "series_fit": 2,
                "monetization_fit": 2,
                "rights_risk": 5,
                "production_effort": 5,
            },
            "Fast-moving rumor topic is risky, weakly sourced, and outside the stable evergreen format.",
            "Reject unless verified sources and rights-safe assets are available.",
            "Avoid live rumor chasing; no live trend scraping or search-volume API integration in this contract.",
        ),
    ]

    calendar_entries = [
        {
            "topic_id": "topic-neymar-2014-pressure",
            "publish_window": "week_01_primary_longform_slot",
            "platform": "youtube_long_form",
            "series": "Football Pressure Index",
            "priority": "high",
            "dependencies": ["rights_review", "source_attribution", "thumbnail_concepts", "p29_editorial_review"],
            "review_status": "needs_review_before_production",
        },
        {
            "topic_id": "topic-messi-2022-pressure",
            "publish_window": "week_02_primary_longform_slot",
            "platform": "youtube_long_form",
            "series": "Legacy vs Future",
            "priority": "high",
            "dependencies": ["rights_review", "source_attribution", "script_fact_check", "p29_editorial_review"],
            "review_status": "needs_review_before_production",
        },
        {
            "topic_id": "topic-world-cup-what-if-2010",
            "publish_window": "research_backlog",
            "platform": "youtube_long_form",
            "series": "World Cup What Ifs",
            "priority": "medium",
            "dependencies": ["additional_research", "counterfactual_guardrails", "rights_review"],
            "review_status": "needs_research",
        },
        {
            "topic_id": "topic-transfer-rumor-live",
            "publish_window": "not_scheduled",
            "platform": "none",
            "series": "The Moment That Changed",
            "priority": "reject_high_risk",
            "dependencies": ["verified_sources_missing", "rights_review_missing"],
            "review_status": "reject_high_risk",
        },
    ]

    return {
        "schema_version": TOPIC_CALENDAR_SCHEMA_VERSION,
        "parent_epic": 330,
        "content_type": "topic_scoring_and_calendar_contract",
        "scoring_rubric": {
            "score_range": "1_to_5",
            "dimensions": {
                "timeliness": {"higher_is_better": True, "description": "How relevant the topic is to the current football conversation."},
                "search_demand": {"higher_is_better": True, "description": "Estimated search and evergreen discovery potential without live API data."},
                "emotional_intensity": {"higher_is_better": True, "description": "Strength of pressure, conflict, nostalgia, shock, or legacy stakes."},
                "comment_potential": {"higher_is_better": True, "description": "Likelihood that the topic creates healthy debate and comments."},
                "series_fit": {"higher_is_better": True, "description": "Fit with approved repeatable P28 series formats."},
                "monetization_fit": {"higher_is_better": True, "description": "Brand safety and long-form monetization suitability."},
                "rights_risk": {"higher_is_better": False, "description": "Rights, footage, music, source, or claim risk."},
                "production_effort": {"higher_is_better": False, "description": "Expected research, scripting, design, and editing effort."},
            },
        },
        "recommendation_states": list(RECOMMENDATION_STATES),
        "scored_topics": scored_topics,
        "content_calendar": calendar_entries,
        "calendar_contract": {
            "required_fields": list(CONTENT_CALENDAR_FIELDS),
            "allowed_platforms": ["youtube_long_form", "youtube_shorts", "tiktok", "instagram_reels", "facebook_reels", "x_twitter", "none"],
            "review_statuses": ["needs_review_before_production", "needs_research", "reject_high_risk", "approved_after_review"],
            "publishing_automation_out_of_scope": True,
            "live_trend_scraping_out_of_scope": True,
            "youtube_search_volume_api_out_of_scope": True,
        },
        "series_connection": {
            "series_metadata_path": "docs/operations/p28-series-metadata-example.json",
            "allowed_series": list(REQUIRED_SERIES_NAMES),
        },
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


def validate_topic_calendar_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the P28 topic scoring and content calendar contract."""

    errors: list[str] = []

    _require(contract.get("schema_version") == TOPIC_CALENDAR_SCHEMA_VERSION, errors, "schema_version mismatch")
    _require(contract.get("parent_epic") == 330, errors, "parent epic must be 330")
    _require(contract.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(contract.get("review_required") is True, errors, "review_required must remain true")

    rubric = contract.get("scoring_rubric", {})
    dimensions = rubric.get("dimensions", {}) if isinstance(rubric, dict) else {}
    _require(set(SCORING_DIMENSIONS) <= set(dimensions), errors, "missing required scoring dimensions")
    for dimension in SCORING_DIMENSIONS:
        dimension_contract = dimensions.get(dimension, {}) if isinstance(dimensions, dict) else {}
        _require(isinstance(dimension_contract, dict), errors, f"{dimension} dimension must be an object")
        if isinstance(dimension_contract, dict):
            _require("higher_is_better" in dimension_contract, errors, f"{dimension} missing higher_is_better")
            _require(bool(dimension_contract.get("description")), errors, f"{dimension} missing description")

    _require(tuple(contract.get("recommendation_states", [])) == RECOMMENDATION_STATES, errors, "recommendation states mismatch")

    scored_topics = contract.get("scored_topics", [])
    _require(isinstance(scored_topics, list) and bool(scored_topics), errors, "scored_topics must be a non-empty list")
    for topic in scored_topics if isinstance(scored_topics, list) else []:
        _require(isinstance(topic, dict), errors, "scored topic must be an object")
        if not isinstance(topic, dict):
            continue
        _require(set(REQUIRED_TOPIC_FIELDS) <= set(topic), errors, "scored topic missing required fields")
        scores = topic.get("scores", {})
        if not isinstance(scores, dict):
            scores = {}
        _require(set(SCORING_DIMENSIONS) <= set(scores), errors, "topic missing scoring dimensions")
        for dimension in SCORING_DIMENSIONS:
            score = scores.get(dimension)
            _require(isinstance(score, int) and 1 <= score <= 5, errors, f"{dimension} score must be 1-5")
        _require(topic.get("recommendation_state") in RECOMMENDATION_STATES, errors, "invalid recommendation_state")
        _require(topic.get("series") in REQUIRED_SERIES_NAMES, errors, "topic series must match approved series")
        _require(topic.get("publish_allowed") is False, errors, "topic publish_allowed must remain false")
        _require(topic.get("review_required") is True, errors, "topic review_required must remain true")

    calendar = contract.get("content_calendar", [])
    _require(isinstance(calendar, list) and bool(calendar), errors, "content_calendar must be a non-empty list")
    for entry in calendar if isinstance(calendar, list) else []:
        _require(isinstance(entry, dict), errors, "calendar entry must be an object")
        if not isinstance(entry, dict):
            continue
        _require(set(CONTENT_CALENDAR_FIELDS) <= set(entry), errors, "calendar entry missing required fields")
        _require(entry.get("series") in REQUIRED_SERIES_NAMES, errors, "calendar series must match approved series")
        _require(isinstance(entry.get("dependencies"), list), errors, "calendar dependencies must be a list")
        _require(bool(entry.get("review_status")), errors, "calendar review_status required")

    calendar_contract = contract.get("calendar_contract", {})
    if not isinstance(calendar_contract, dict):
        calendar_contract = {}
    _require(set(CONTENT_CALENDAR_FIELDS) <= set(calendar_contract.get("required_fields", [])), errors, "calendar contract missing required fields")
    _require(calendar_contract.get("publishing_automation_out_of_scope") is True, errors, "publishing automation must be out of scope")
    _require(calendar_contract.get("live_trend_scraping_out_of_scope") is True, errors, "live trend scraping must be out of scope")
    _require(calendar_contract.get("youtube_search_volume_api_out_of_scope") is True, errors, "YouTube search-volume API must be out of scope")

    series_connection = contract.get("series_connection", {})
    if not isinstance(series_connection, dict):
        series_connection = {}
    _require(series_connection.get("series_metadata_path") == "docs/operations/p28-series-metadata-example.json", errors, "series metadata connection required")
    _require(set(REQUIRED_SERIES_NAMES) <= set(series_connection.get("allowed_series", [])), errors, "allowed series missing required names")

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
        "schema_version": TOPIC_CALENDAR_VALIDATION_SCHEMA_VERSION,
        "is_valid": not errors,
        "scoring_dimensions_checked": list(SCORING_DIMENSIONS),
        "recommendation_states_checked": list(RECOMMENDATION_STATES),
        "calendar_fields_checked": list(CONTENT_CALENDAR_FIELDS),
        "topic_count": len(scored_topics) if isinstance(scored_topics, list) else 0,
        "calendar_entry_count": len(calendar) if isinstance(calendar, list) else 0,
        "publish_allowed": False,
        "review_required": True,
        "errors": errors,
    }
