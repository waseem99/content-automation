"""P31 operator reporting and decision brief contracts.

P31 converts existing package, export, governance, and analytics feedback artifacts
into operator-readable reports. It does not build dashboards, deliver emails or
Slack messages, ingest live analytics APIs, sync real account data, or execute
publishing decisions.
"""

from __future__ import annotations

from typing import Any

P31_CONTRACT_VERSION = "p31.operator_reporting.v1"
P31_VALIDATION_VERSION = "p31.operator_reporting_validation.v1"

REPORTING_INPUT_FIELDS = (
    "reporting_period",
    "generated_at",
    "content_packages",
    "export_manifests",
    "publish_readiness_manifests",
    "analytics_feedback_snapshots",
    "governance_exceptions",
    "recommendations",
    "operator_notes",
)

UPSTREAM_LINKS = (
    "p27_export_packs",
    "p28_topic_planning",
    "p29_publish_governance",
    "p30_analytics_feedback",
)

WEEKLY_BRIEF_FIELDS = (
    "reporting_period",
    "executive_summary",
    "channel_health",
    "top_performers",
    "weak_performers",
    "audience_signals",
    "learning_summary",
    "recommended_focus_next_week",
    "review_required_items",
)

DECISION_QUEUE_FIELDS = (
    "item_id",
    "content_id",
    "decision_type",
    "priority",
    "reason",
    "source_signal",
    "recommended_action",
    "owner_role",
    "due_window",
    "review_status",
)

DECISION_TYPES = (
    "repeat",
    "revise",
    "expand",
    "hold",
    "archive",
    "escalate_rights",
    "escalate_risk",
    "prepare_export",
)

EXCEPTION_FIELDS = (
    "exception_id",
    "content_id",
    "severity",
    "blocker_type",
    "governance_source",
    "current_status",
    "required_resolution",
    "owner_role",
    "review_notes",
)

SEVERITY_LEVELS = ("low", "medium", "high", "critical")

HANDOFF_FIELDS = (
    "package_id",
    "reporting_period",
    "generated_at",
    "files",
    "audience",
    "review_required",
    "distribution_note",
    "next_operator_steps",
)

HANDOFF_FILES = (
    "weekly_brief.json",
    "decision_queue.json",
    "governance_exceptions.json",
    "operator_summary.md",
)


def build_p31_operator_reporting_contract() -> dict[str, Any]:
    """Build the deterministic P31 operator reporting contract."""

    return {
        "schema_version": P31_CONTRACT_VERSION,
        "parent_epic": 419,
        "content_type": "operator_reporting_contract",
        "reporting_input_bundle": {
            "issue": 420,
            "required_fields": list(REPORTING_INPUT_FIELDS),
            "upstream_links": list(UPSTREAM_LINKS),
            "example": {
                "reporting_period": "2026-W28",
                "generated_at": "2026-07-09T00:00:00Z",
                "content_packages": ["content_package_neymar_short.json", "content_package_ghana_longform.json"],
                "export_manifests": ["exports/youtube_shorts/package.json", "exports/youtube_long_form/package.json"],
                "publish_readiness_manifests": ["p29-publish-readiness-manifest-example.json"],
                "analytics_feedback_snapshots": ["p30-analytics-feedback-example.json"],
                "governance_exceptions": ["rights_review_required", "blocked_from_learning"],
                "recommendations": ["create_follow_up_short", "refine_angle"],
                "operator_notes": "Manual fixture-based report; no live account data or API ingestion.",
                "manual_or_fixture_based": True,
                "live_api_ingested": False,
                "automated_notification_sent": False,
            },
        },
        "weekly_channel_brief": {
            "issue": 421,
            "required_fields": list(WEEKLY_BRIEF_FIELDS),
            "example": {
                "reporting_period": "2026-W28",
                "executive_summary": "Legacy debate Shorts performed strongly; long-form packaging needs refinement.",
                "channel_health": "stable_with_shorts_momentum",
                "top_performers": ["episode-neymar-2014-short-01"],
                "weak_performers": ["episode-ghana-2010-what-if"],
                "audience_signals": ["high comments on player legacy", "weak CTR on generic what-if thumbnail"],
                "learning_summary": "Emotional legacy hooks create debate; long-form needs clearer stakes in title/cover.",
                "recommended_focus_next_week": ["produce follow-up Neymar legacy Short", "revise Ghana long-form title and cover"],
                "review_required_items": ["rights review for follow-up imagery", "thumbnail copy review"],
                "not_dashboard": True,
                "automated_delivery": False,
            },
        },
        "content_decision_queue": {
            "issue": 422,
            "required_fields": list(DECISION_QUEUE_FIELDS),
            "decision_types": list(DECISION_TYPES),
            "items": [
                {
                    "item_id": "decision-001",
                    "content_id": "episode-neymar-2014-short-01",
                    "decision_type": "repeat",
                    "priority": "high",
                    "reason": "Outperforming comments and shares.",
                    "source_signal": "P30 learning snapshot: outperforming",
                    "recommended_action": "Create one follow-up Short with clearer source notes.",
                    "owner_role": "content_operator",
                    "due_window": "next_week",
                    "review_status": "review_required",
                    "automatically_executed": False,
                },
                {
                    "item_id": "decision-002",
                    "content_id": "episode-ghana-2010-what-if",
                    "decision_type": "revise",
                    "priority": "medium",
                    "reason": "Weak click-through rate with acceptable retention.",
                    "source_signal": "P30 packaging iteration recommendation",
                    "recommended_action": "Revise title and thumbnail/cover before another push.",
                    "owner_role": "editorial_operator",
                    "due_window": "next_week",
                    "review_status": "review_required",
                    "automatically_executed": False,
                },
                {
                    "item_id": "decision-003",
                    "content_id": "unreviewed-transfer-rumor-short",
                    "decision_type": "archive",
                    "priority": "high",
                    "reason": "Blocked from learning due to unreviewed factual claim.",
                    "source_signal": "P30 blocked_from_learning outcome",
                    "recommended_action": "Archive or rewrite with verified sources.",
                    "owner_role": "risk_reviewer",
                    "due_window": "immediate_review",
                    "review_status": "review_required",
                    "automatically_executed": False,
                },
            ],
        },
        "risk_governance_exceptions": {
            "issue": 423,
            "required_fields": list(EXCEPTION_FIELDS),
            "severity_levels": list(SEVERITY_LEVELS),
            "exceptions": [
                {
                    "exception_id": "exception-001",
                    "content_id": "unreviewed-transfer-rumor-short",
                    "severity": "high",
                    "blocker_type": "unreviewed_factual_claim",
                    "governance_source": "p30_blocked_from_learning",
                    "current_status": "blocked",
                    "required_resolution": "Verify sources or archive item.",
                    "owner_role": "risk_reviewer",
                    "review_notes": "Do not use performance learning from unsafe rumor content.",
                    "automatic_platform_action": False,
                },
                {
                    "exception_id": "exception-002",
                    "content_id": "episode-ghana-2010-what-if",
                    "severity": "medium",
                    "blocker_type": "rights_review_required",
                    "governance_source": "p29_publish_governance",
                    "current_status": "review_required",
                    "required_resolution": "Confirm rights-cleared imagery before cover update.",
                    "owner_role": "rights_reviewer",
                    "review_notes": "Packaging revision cannot become export-ready until rights review passes.",
                    "automatic_platform_action": False,
                },
            ],
        },
        "operator_handoff_package": {
            "issue": 424,
            "required_fields": list(HANDOFF_FIELDS),
            "required_files": list(HANDOFF_FILES),
            "example": {
                "package_id": "operator-report-2026-W28",
                "reporting_period": "2026-W28",
                "generated_at": "2026-07-09T00:00:00Z",
                "files": list(HANDOFF_FILES),
                "audience": ["content_operator", "editorial_operator", "risk_reviewer"],
                "review_required": True,
                "distribution_note": "Local/review-only artifact. No email, Slack, dashboard, or external upload is performed.",
                "next_operator_steps": ["review decision queue", "resolve governance exceptions", "approve or reject next-week focus"],
                "external_distribution_performed": False,
            },
        },
        "closeout": {
            "issue": 425,
            "child_tasks": [420, 421, 422, 423, 424, 425],
            "no_dashboard_ui": True,
            "no_email_slack_automation": True,
            "no_live_api_ingestion": True,
            "no_external_distribution": True,
            "no_auto_publish_path": True,
            "review_required": True,
        },
        "publish_allowed": False,
        "review_required": True,
    }


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_p31_operator_reporting_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate the P31 operator reporting contract."""

    errors: list[str] = []
    _require(contract.get("schema_version") == P31_CONTRACT_VERSION, errors, "schema_version mismatch")
    _require(contract.get("parent_epic") == 419, errors, "parent epic must be 419")
    _require(contract.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(contract.get("review_required") is True, errors, "review_required must remain true")

    bundle = contract.get("reporting_input_bundle", {})
    _require(set(REPORTING_INPUT_FIELDS) <= set(bundle.get("required_fields", [])), errors, "reporting input fields missing")
    _require(set(UPSTREAM_LINKS) <= set(bundle.get("upstream_links", [])), errors, "upstream links missing")
    bundle_example = bundle.get("example", {})
    _require(set(REPORTING_INPUT_FIELDS) <= set(bundle_example), errors, "reporting input example missing fields")
    _require(bundle_example.get("manual_or_fixture_based") is True, errors, "bundle must remain manual/fixture based")
    _require(bundle_example.get("live_api_ingested") is False, errors, "bundle must not ingest live APIs")
    _require(bundle_example.get("automated_notification_sent") is False, errors, "bundle must not send notifications")

    brief = contract.get("weekly_channel_brief", {})
    _require(set(WEEKLY_BRIEF_FIELDS) <= set(brief.get("required_fields", [])), errors, "weekly brief fields missing")
    brief_example = brief.get("example", {})
    _require(set(WEEKLY_BRIEF_FIELDS) <= set(brief_example), errors, "weekly brief example missing fields")
    _require(brief_example.get("not_dashboard") is True, errors, "weekly brief must not be dashboard")
    _require(brief_example.get("automated_delivery") is False, errors, "weekly brief must not auto-deliver")

    queue = contract.get("content_decision_queue", {})
    _require(set(DECISION_QUEUE_FIELDS) <= set(queue.get("required_fields", [])), errors, "decision queue fields missing")
    _require(set(DECISION_TYPES) <= set(queue.get("decision_types", [])), errors, "decision types missing")
    for item in queue.get("items", []):
        _require(set(DECISION_QUEUE_FIELDS) <= set(item), errors, "decision item missing fields")
        _require(item.get("decision_type") in DECISION_TYPES, errors, "unsupported decision type")
        _require(item.get("review_status") == "review_required", errors, "decision item must require review")
        _require(item.get("automatically_executed") is False, errors, "decision item must not execute automatically")

    exceptions = contract.get("risk_governance_exceptions", {})
    _require(set(EXCEPTION_FIELDS) <= set(exceptions.get("required_fields", [])), errors, "exception fields missing")
    _require(set(SEVERITY_LEVELS) <= set(exceptions.get("severity_levels", [])), errors, "severity levels missing")
    for exception in exceptions.get("exceptions", []):
        _require(set(EXCEPTION_FIELDS) <= set(exception), errors, "exception item missing fields")
        _require(exception.get("severity") in SEVERITY_LEVELS, errors, "unsupported severity")
        _require(exception.get("automatic_platform_action") is False, errors, "exception must not trigger platform action")

    handoff = contract.get("operator_handoff_package", {})
    _require(set(HANDOFF_FIELDS) <= set(handoff.get("required_fields", [])), errors, "handoff fields missing")
    _require(set(HANDOFF_FILES) <= set(handoff.get("required_files", [])), errors, "handoff files missing")
    handoff_example = handoff.get("example", {})
    _require(set(HANDOFF_FIELDS) <= set(handoff_example), errors, "handoff example missing fields")
    _require(set(HANDOFF_FILES) <= set(handoff_example.get("files", [])), errors, "handoff example files missing")
    _require(handoff_example.get("review_required") is True, errors, "handoff must require review")
    _require(handoff_example.get("external_distribution_performed") is False, errors, "handoff must not distribute externally")

    closeout = contract.get("closeout", {})
    _require(closeout.get("child_tasks") == [420, 421, 422, 423, 424, 425], errors, "P31 child task list mismatch")
    _require(closeout.get("no_dashboard_ui") is True, errors, "dashboard exclusion missing")
    _require(closeout.get("no_email_slack_automation") is True, errors, "email/slack exclusion missing")
    _require(closeout.get("no_live_api_ingestion") is True, errors, "live API exclusion missing")
    _require(closeout.get("no_external_distribution") is True, errors, "external distribution exclusion missing")
    _require(closeout.get("no_auto_publish_path") is True, errors, "auto-publish exclusion missing")
    _require(closeout.get("review_required") is True, errors, "closeout review requirement missing")

    return {
        "schema_version": P31_VALIDATION_VERSION,
        "is_valid": not errors,
        "reporting_input_fields_checked": list(REPORTING_INPUT_FIELDS),
        "weekly_brief_fields_checked": list(WEEKLY_BRIEF_FIELDS),
        "decision_queue_fields_checked": list(DECISION_QUEUE_FIELDS),
        "exception_fields_checked": list(EXCEPTION_FIELDS),
        "handoff_fields_checked": list(HANDOFF_FIELDS),
        "publish_allowed": False,
        "review_required": True,
        "errors": errors,
    }
