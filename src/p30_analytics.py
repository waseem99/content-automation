"""P30 analytics feedback and performance learning contracts.

P30 is a review-safe analytics feedback layer. It supports manual or fixture-based
metrics records, learning snapshots, advisory topic feedback, packaging iteration
recommendations, and future API boundary documentation. It does not ingest live
platform data, store credentials, authenticate users, or automate publishing.
"""

from __future__ import annotations

from typing import Any

P30_CONTRACT_VERSION = "p30.analytics_feedback.v1"
P30_VALIDATION_VERSION = "p30.analytics_feedback_validation.v1"

METRIC_FIELDS = (
    "platform",
    "content_id",
    "published_external_url",
    "publish_date",
    "views",
    "watch_time_seconds",
    "average_view_duration_seconds",
    "retention_rate",
    "likes",
    "comments",
    "shares",
    "saves",
    "click_through_rate",
    "subscribers_gained",
    "revenue_estimate",
    "manual_notes",
    "review_state",
    "data_quality",
)

SUPPORTED_FORMATS = ("shorts", "explainer", "long_form")
SUPPORTED_PLATFORMS = (
    "youtube_shorts",
    "youtube_long_form",
    "tiktok",
    "instagram_reels",
    "facebook_reels",
    "x_twitter",
)

OUTCOME_LABELS = (
    "outperforming",
    "average",
    "underperforming",
    "inconclusive",
    "blocked_from_learning",
)

OUTCOME_FIELDS = (
    "content_id",
    "format",
    "platform",
    "performance_window",
    "baseline_comparison",
    "outcome_label",
    "winning_elements",
    "weak_elements",
    "audience_signal_summary",
    "reviewer_interpretation",
    "recommended_follow_up",
)

RECOMMENDATION_OUTPUTS = (
    "repeat_format",
    "refine_angle",
    "expand_to_long_form",
    "create_follow_up_short",
    "hold",
    "reject_or_archive",
)

P28_SCORE_LINKS = (
    "timeliness",
    "emotional_intensity",
    "comment_potential",
    "series_fit",
    "monetization_fit",
    "production_effort",
)

ITERATION_FIELDS = (
    "content_id",
    "source_metric_signal",
    "element_type",
    "current_version",
    "proposed_change",
    "rationale",
    "risk_note",
    "expected_learning",
    "review_status",
)

ITERATION_ELEMENT_TYPES = (
    "hook",
    "title",
    "thumbnail_cover",
    "caption",
    "pinned_comment",
    "description",
    "series_positioning",
)

FUTURE_API_CANDIDATES = (
    "youtube_analytics",
    "tiktok_analytics",
    "instagram_facebook_insights",
    "x_twitter_analytics",
    "external_dashboards",
)

FUTURE_API_SAFEGUARDS = (
    "oauth_scope_review",
    "token_storage_policy",
    "user_consent",
    "rate_limits",
    "privacy_review",
    "audit_logging",
    "manual_override",
)


def build_p30_analytics_feedback_contract() -> dict[str, Any]:
    """Build the deterministic P30 analytics feedback contract."""

    return {
        "schema_version": P30_CONTRACT_VERSION,
        "parent_epic": 411,
        "content_type": "analytics_feedback_contract",
        "metrics_input_contract": {
            "issue": 412,
            "required_fields": list(METRIC_FIELDS),
            "supported_formats": list(SUPPORTED_FORMATS),
            "supported_platforms": list(SUPPORTED_PLATFORMS),
            "records": [
                {
                    "platform": "youtube_shorts",
                    "content_id": "episode-neymar-2014-short-01",
                    "published_external_url": "manual-entry-only",
                    "publish_date": "2026-07-01",
                    "views": 125000,
                    "watch_time_seconds": 420000,
                    "average_view_duration_seconds": 21.5,
                    "retention_rate": 0.72,
                    "likes": 9200,
                    "comments": 830,
                    "shares": 510,
                    "saves": 240,
                    "click_through_rate": 0.054,
                    "subscribers_gained": 940,
                    "revenue_estimate": 0.0,
                    "manual_notes": "Strong debate around Neymar legacy and Brazil pressure.",
                    "review_state": "human_reviewed",
                    "data_quality": "manual_verified",
                    "format": "shorts",
                    "live_api_ingested": False,
                    "credential_storage_used": False,
                },
                {
                    "platform": "youtube_long_form",
                    "content_id": "episode-ghana-2010-what-if",
                    "published_external_url": "manual-entry-only",
                    "publish_date": "2026-07-03",
                    "views": 18000,
                    "watch_time_seconds": 172800,
                    "average_view_duration_seconds": 192.0,
                    "retention_rate": 0.41,
                    "likes": 720,
                    "comments": 122,
                    "shares": 61,
                    "saves": 88,
                    "click_through_rate": 0.028,
                    "subscribers_gained": 61,
                    "revenue_estimate": 4.25,
                    "manual_notes": "Good comments but weak thumbnail click-through.",
                    "review_state": "human_reviewed",
                    "data_quality": "manual_estimate",
                    "format": "long_form",
                    "live_api_ingested": False,
                    "credential_storage_used": False,
                },
            ],
        },
        "learning_snapshot_contract": {
            "issue": 413,
            "required_fields": list(OUTCOME_FIELDS),
            "outcome_labels": list(OUTCOME_LABELS),
            "snapshots": [
                {
                    "content_id": "episode-neymar-2014-short-01",
                    "format": "shorts",
                    "platform": "youtube_shorts",
                    "performance_window": "7d",
                    "baseline_comparison": "above_channel_short_median",
                    "outcome_label": "outperforming",
                    "winning_elements": ["legacy debate hook", "high comment prompt"],
                    "weak_elements": ["limited source context"],
                    "audience_signal_summary": "High comments and shares show strong emotional debate.",
                    "reviewer_interpretation": "Repeat player legacy pressure angles with clearer source notes.",
                    "recommended_follow_up": "create_follow_up_short",
                },
                {
                    "content_id": "episode-ghana-2010-what-if",
                    "format": "long_form",
                    "platform": "youtube_long_form",
                    "performance_window": "7d",
                    "baseline_comparison": "near_channel_longform_median",
                    "outcome_label": "average",
                    "winning_elements": ["what-if premise", "comment debate"],
                    "weak_elements": ["thumbnail clarity", "opening pace"],
                    "audience_signal_summary": "Retention was acceptable but click-through was weak.",
                    "reviewer_interpretation": "Refine title and thumbnail before expanding similar topics.",
                    "recommended_follow_up": "refine_angle",
                },
                {
                    "content_id": "unreviewed-transfer-rumor-short",
                    "format": "shorts",
                    "platform": "tiktok",
                    "performance_window": "not_applicable",
                    "baseline_comparison": "not_applicable",
                    "outcome_label": "blocked_from_learning",
                    "winning_elements": [],
                    "weak_elements": ["unreviewed factual claim"],
                    "audience_signal_summary": "Blocked by review; do not learn from unsafe input.",
                    "reviewer_interpretation": "Archive unsafe rumor format.",
                    "recommended_follow_up": "reject_or_archive",
                },
            ],
        },
        "topic_feedback_rules": {
            "issue": 414,
            "p28_score_links": list(P28_SCORE_LINKS),
            "recommendation_outputs": list(RECOMMENDATION_OUTPUTS),
            "rules": [
                {
                    "rule_id": "high-comments-repeat-format",
                    "if": "outperforming with high comments and shares",
                    "then": "repeat_format",
                    "score_adjustments": {"comment_potential": 1, "emotional_intensity": 1, "series_fit": 1},
                    "requires_human_review": True,
                },
                {
                    "rule_id": "weak-ctr-refine-packaging",
                    "if": "average or underperforming with weak click_through_rate",
                    "then": "refine_angle",
                    "score_adjustments": {"production_effort": 1},
                    "requires_human_review": True,
                },
                {
                    "rule_id": "blocked-content-archive",
                    "if": "blocked_from_learning or unsafe source/risk state",
                    "then": "reject_or_archive",
                    "score_adjustments": {"monetization_fit": -2},
                    "requires_human_review": True,
                },
            ],
        },
        "packaging_iteration_contract": {
            "issue": 415,
            "required_fields": list(ITERATION_FIELDS),
            "element_types": list(ITERATION_ELEMENT_TYPES),
            "recommendations": [
                {
                    "content_id": "episode-ghana-2010-what-if",
                    "source_metric_signal": "low click_through_rate",
                    "element_type": "title",
                    "current_version": "What If Ghana Won in 2010?",
                    "proposed_change": "The Penalty That Could Have Changed African Football Forever",
                    "rationale": "Make the emotional stakes clearer.",
                    "risk_note": "Keep sourced what-if framing; avoid claiming alternate history as fact.",
                    "expected_learning": "Measure click-through change after human-approved packaging update.",
                    "review_status": "review_required",
                },
                {
                    "content_id": "episode-neymar-2014-short-01",
                    "source_metric_signal": "high early retention",
                    "element_type": "hook",
                    "current_version": "Was Neymar carrying Brazil?",
                    "proposed_change": "Brazil did not just lose Neymar. They lost their pressure valve.",
                    "rationale": "Test a sharper emotional hook while staying factual.",
                    "risk_note": "Review tone and factual context before reuse.",
                    "expected_learning": "Compare retention and comments on follow-up Short.",
                    "review_status": "review_required",
                },
                {
                    "content_id": "episode-ghana-2010-what-if",
                    "source_metric_signal": "weak thumbnail clarity",
                    "element_type": "thumbnail_cover",
                    "current_version": "Penalty image with generic text",
                    "proposed_change": "Use a clean penalty moment cover with one clear question.",
                    "rationale": "Improve visual clarity for long-form browsing.",
                    "risk_note": "Use rights-cleared or licensed imagery only.",
                    "expected_learning": "Compare click-through after manual packaging review.",
                    "review_status": "review_required",
                },
            ],
        },
        "future_api_boundary": {
            "issue": 416,
            "api_candidates": list(FUTURE_API_CANDIDATES),
            "required_safeguards": list(FUTURE_API_SAFEGUARDS),
            "current_support": "manual_or_fixture_metrics_only",
            "live_api_ingestion_enabled": False,
            "oauth_implemented": False,
            "credential_storage_used": False,
            "real_account_data_ingested": False,
        },
        "closeout": {
            "issue": 417,
            "child_tasks": [412, 413, 414, 415, 416, 417],
            "no_live_analytics_ingestion": True,
            "no_api_credential_storage": True,
            "no_auto_publish_path": True,
            "human_review_required": True,
        },
        "publish_allowed": False,
        "review_required": True,
    }


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_p30_analytics_feedback_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the P30 analytics feedback contract."""

    errors: list[str] = []
    _require(contract.get("schema_version") == P30_CONTRACT_VERSION, errors, "schema_version mismatch")
    _require(contract.get("parent_epic") == 411, errors, "parent epic must be 411")
    _require(contract.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(contract.get("review_required") is True, errors, "review_required must remain true")

    metrics = contract.get("metrics_input_contract", {})
    _require(set(METRIC_FIELDS) <= set(metrics.get("required_fields", [])), errors, "metrics fields missing")
    _require(set(SUPPORTED_FORMATS) <= set(metrics.get("supported_formats", [])), errors, "supported formats missing")
    _require(set(SUPPORTED_PLATFORMS) <= set(metrics.get("supported_platforms", [])), errors, "supported platforms missing")
    for record in metrics.get("records", []):
        _require(set(METRIC_FIELDS) <= set(record), errors, "metrics record missing fields")
        _require(record.get("live_api_ingested") is False, errors, "live API ingestion must remain false")
        _require(record.get("credential_storage_used") is False, errors, "credential storage must remain false")

    snapshots = contract.get("learning_snapshot_contract", {})
    _require(set(OUTCOME_FIELDS) <= set(snapshots.get("required_fields", [])), errors, "outcome fields missing")
    _require(set(OUTCOME_LABELS) <= set(snapshots.get("outcome_labels", [])), errors, "outcome labels missing")
    seen_outcomes = [snapshot.get("outcome_label") for snapshot in snapshots.get("snapshots", [])]
    _require("outperforming" in seen_outcomes, errors, "strong outcome example missing")
    _require("average" in seen_outcomes or "underperforming" in seen_outcomes, errors, "weak or average outcome example missing")
    _require("blocked_from_learning" in seen_outcomes or "inconclusive" in seen_outcomes, errors, "inconclusive/blocked outcome example missing")

    feedback = contract.get("topic_feedback_rules", {})
    _require(set(P28_SCORE_LINKS) <= set(feedback.get("p28_score_links", [])), errors, "P28 score links missing")
    _require(set(RECOMMENDATION_OUTPUTS) <= set(feedback.get("recommendation_outputs", [])), errors, "recommendation outputs missing")
    for rule in feedback.get("rules", []):
        _require(rule.get("then") in RECOMMENDATION_OUTPUTS, errors, "invalid recommendation output")
        _require(rule.get("requires_human_review") is True, errors, "feedback rule must require human review")

    iteration = contract.get("packaging_iteration_contract", {})
    _require(set(ITERATION_FIELDS) <= set(iteration.get("required_fields", [])), errors, "iteration fields missing")
    _require(set(ITERATION_ELEMENT_TYPES) <= set(iteration.get("element_types", [])), errors, "iteration element types missing")
    seen_elements = [item.get("element_type") for item in iteration.get("recommendations", [])]
    _require("hook" in seen_elements, errors, "hook recommendation missing")
    _require("title" in seen_elements, errors, "title recommendation missing")
    _require("thumbnail_cover" in seen_elements, errors, "thumbnail/cover recommendation missing")
    for item in iteration.get("recommendations", []):
        _require(set(ITERATION_FIELDS) <= set(item), errors, "iteration recommendation missing fields")
        _require(item.get("review_status") == "review_required", errors, "iteration recommendation must require review")

    boundary = contract.get("future_api_boundary", {})
    _require(set(FUTURE_API_CANDIDATES) <= set(boundary.get("api_candidates", [])), errors, "future API candidates missing")
    _require(set(FUTURE_API_SAFEGUARDS) <= set(boundary.get("required_safeguards", [])), errors, "future API safeguards missing")
    _require(boundary.get("current_support") == "manual_or_fixture_metrics_only", errors, "current support must remain manual/fixture only")
    _require(boundary.get("live_api_ingestion_enabled") is False, errors, "live API ingestion must remain disabled")
    _require(boundary.get("oauth_implemented") is False, errors, "OAuth must remain unimplemented")
    _require(boundary.get("credential_storage_used") is False, errors, "credential storage must remain false")
    _require(boundary.get("real_account_data_ingested") is False, errors, "real account data ingestion must remain false")

    closeout = contract.get("closeout", {})
    _require(closeout.get("child_tasks") == [412, 413, 414, 415, 416, 417], errors, "P30 child tasks mismatch")
    _require(closeout.get("no_live_analytics_ingestion") is True, errors, "no live analytics ingestion confirmation missing")
    _require(closeout.get("no_api_credential_storage") is True, errors, "no API credential storage confirmation missing")
    _require(closeout.get("no_auto_publish_path") is True, errors, "no auto-publish path confirmation missing")
    _require(closeout.get("human_review_required") is True, errors, "human review requirement missing")

    return {
        "schema_version": P30_VALIDATION_VERSION,
        "is_valid": not errors,
        "metrics_fields_checked": list(METRIC_FIELDS),
        "outcome_fields_checked": list(OUTCOME_FIELDS),
        "recommendation_outputs_checked": list(RECOMMENDATION_OUTPUTS),
        "iteration_fields_checked": list(ITERATION_FIELDS),
        "future_api_safeguards_checked": list(FUTURE_API_SAFEGUARDS),
        "publish_allowed": False,
        "review_required": True,
        "errors": errors,
    }
