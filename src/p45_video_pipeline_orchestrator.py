"""P45 end-to-end video content pipeline orchestrator.

This module runs the local pipeline from one input brief through P40, P41, P42,
P43, and P44. It returns a deterministic, JSON-serializable package containing
all intermediate outputs plus final status, blockers, next actions, and safety
guardrails.

It does not call external APIs, render/edit video, download assets, upload,
publish, ingest live analytics, or guarantee monetization/revenue.
"""

from __future__ import annotations

from typing import Any

from src.p40_video_content_engine import generate_video_package
from src.p41_rights_safety_engine import analyze_rights_safety
from src.p42_engagement_retention_engine import build_engagement_scorecard
from src.p43_production_pack_engine import build_production_handoff_pack
from src.p44_monetization_readiness_engine import build_monetization_readiness_report

P45_PIPELINE_VERSION = "p45.end_to_end_video_pipeline.v1"


def run_video_content_pipeline(brief: dict[str, Any]) -> dict[str, Any]:
    """Run the full local video content pipeline from one brief."""

    video_package = generate_video_package(brief)
    if not video_package.get("is_valid"):
        return {
            "schema_version": P45_PIPELINE_VERSION,
            "is_valid": False,
            "pipeline_status": "invalid_brief",
            "validation_errors": video_package.get("validation_errors", []),
            "video_package": video_package,
            **_guardrails(),
        }

    rights_report = analyze_rights_safety(video_package)
    engagement_scorecard = build_engagement_scorecard(video_package)
    production_pack = build_production_handoff_pack({
        "video_package": video_package,
        "rights_report": rights_report,
        "engagement_scorecard": engagement_scorecard,
    })
    monetization_report = build_monetization_readiness_report({
        "video_package": video_package,
        "rights_report": rights_report,
        "engagement_scorecard": engagement_scorecard,
        "production_pack": production_pack,
    })
    summary = aggregate_pipeline_status(
        video_package,
        rights_report,
        engagement_scorecard,
        production_pack,
        monetization_report,
    )
    return {
        "schema_version": P45_PIPELINE_VERSION,
        "is_valid": True,
        "pipeline_status": summary["pipeline_status"],
        "summary": summary,
        "video_package": video_package,
        "rights_report": rights_report,
        "engagement_scorecard": engagement_scorecard,
        "production_pack": production_pack,
        "monetization_report": monetization_report,
        **_guardrails(),
    }


def aggregate_pipeline_status(
    video_package: dict[str, Any],
    rights_report: dict[str, Any],
    engagement_scorecard: dict[str, Any],
    production_pack: dict[str, Any],
    monetization_report: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate gates, scores, blockers, and next actions."""

    rights_gate = rights_report.get("publish_gate", {}).get("gate", "revise")
    engagement_score = int(engagement_scorecard.get("overall_engagement_score", 0))
    monetization_status = monetization_report.get("final_recommendation", {}).get("status", "needs_packaging_improvement")
    production_ready = bool(production_pack.get("handoff_ready", False))
    blockers = _collect_blockers(rights_report, engagement_scorecard, production_pack, monetization_report)
    next_actions = _collect_next_actions(rights_report, engagement_scorecard, monetization_report)
    if rights_gate == "block" or blockers:
        status = "block"
    elif engagement_score >= 80 and production_ready and monetization_status == "ready_for_human_review":
        status = "ready_for_human_review"
    else:
        status = "revise"
    return {
        "pipeline_status": status,
        "rights_gate": rights_gate,
        "engagement_score": engagement_score,
        "monetization_status": monetization_status,
        "production_ready": production_ready,
        "best_monetization_routes": monetization_report.get("monetization_route_fit", {}).get("best_routes", []),
        "blockers": blockers,
        "next_actions": next_actions,
        "human_review_required_before_publish": True,
        "core_outputs_present": all([
            bool(video_package),
            bool(rights_report),
            bool(engagement_scorecard),
            bool(production_pack),
            bool(monetization_report),
        ]),
    }


def _collect_blockers(
    rights_report: dict[str, Any],
    engagement_scorecard: dict[str, Any],
    production_pack: dict[str, Any],
    monetization_report: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    publish_gate = rights_report.get("publish_gate", {})
    if publish_gate.get("gate") == "block":
        blockers.extend(publish_gate.get("blocker_reasons", []) or ["Rights gate blocked."])
    if int(engagement_scorecard.get("overall_engagement_score", 0)) < 65:
        blockers.append("Engagement score is below minimum production threshold.")
    if not production_pack.get("handoff_ready", False):
        blockers.append("Production handoff pack is not ready.")
    if monetization_report.get("final_recommendation", {}).get("status") == "not_ready":
        blockers.append("Monetization readiness status is not ready.")
    return blockers


def _collect_next_actions(
    rights_report: dict[str, Any],
    engagement_scorecard: dict[str, Any],
    monetization_report: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    actions.extend(rights_report.get("publish_gate", {}).get("required_fixes", []))
    actions.extend(item.get("action", "") for item in engagement_scorecard.get("improvement_plan", []) if item.get("action"))
    actions.extend(monetization_report.get("final_recommendation", {}).get("next_actions", []))
    deduped = []
    for action in actions:
        if action and action not in deduped:
            deduped.append(action)
    return deduped or ["Run final human review before publishing."]


def _guardrails() -> dict[str, Any]:
    return {
        "external_calls_performed": False,
        "rendering_performed": False,
        "asset_download_performed": False,
        "upload_or_publish_performed": False,
        "live_analytics_used": False,
        "monetization_guaranteed": False,
        "revenue_guaranteed": False,
        "human_review_required_before_publish": True,
    }
