"""P44 monetization readiness and channel packaging engine.

This module evaluates a video package across monetization routes and prepares
channel packaging metadata, sponsor/affiliate/lead-gen notes, repurposing plan,
and a final readiness report.

It does not guarantee monetization or revenue, upload/publish content, call
platform APIs, ingest live analytics, or provide legal/tax advice.
"""

from __future__ import annotations

import re
from typing import Any

P44_REPORT_VERSION = "p44.monetization_readiness_report.v1"

ROUTES = ("ad_revenue", "sponsorship", "affiliate", "lead_gen", "product_service", "ip_library")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _words(text: str) -> list[str]:
    return re.findall(r"\b\w+[\w'-]*\b", text.lower())


def normalize_monetization_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize P40/P41/P42/P43 bundle for monetization readiness."""

    video = payload.get("video_package", payload)
    rights = payload.get("rights_report", {})
    engagement = payload.get("engagement_scorecard", {})
    production = payload.get("production_pack", {})
    brief = video.get("brief", {}) if isinstance(video.get("brief"), dict) else {}
    fields = {
        "platform": brief.get("platform") or video.get("platform") or "unknown",
        "topic": brief.get("topic") or video.get("topic") or "video topic",
        "audience": brief.get("audience") or video.get("audience") or "target audience",
        "monetization_goal": brief.get("monetization_goal") or video.get("monetization_goal") or "audience growth",
        "title_options": _as_list(video.get("title_options")),
        "hook": _clean(video.get("hook")),
        "script": _clean(video.get("script")),
        "rights_gate": rights.get("publish_gate", {}),
        "rights_score": rights.get("scores", {}).get("overall_safety_score", 80),
        "engagement_score": engagement.get("overall_engagement_score", video.get("scores", {}).get("engagement_score", 75)),
        "production_ready": bool(production.get("handoff_ready", False)),
        "cta_variants": _as_list(engagement.get("cta_variants")),
        "thumbnail": production.get("thumbnail_directions", {}),
    }
    errors = []
    if not fields["script"] or not fields["title_options"]:
        errors.append("missing_video_package")
    return {"is_valid": not errors, "validation_errors": errors, "fields": fields}


def score_monetization_routes(fields: dict[str, Any]) -> dict[str, Any]:
    text = " ".join([fields["topic"], fields["audience"], fields["monetization_goal"], fields["script"]]).lower()
    rights_gate = fields.get("rights_gate", {})
    gate = rights_gate.get("gate", "pass") if isinstance(rights_gate, dict) else "pass"
    rights_score = int(fields.get("rights_score", 80))
    engagement = int(fields.get("engagement_score", 75))
    production_bonus = 8 if fields.get("production_ready") else 0
    gate_penalty = 35 if gate == "block" else 15 if gate == "revise" else 0
    base = max(0, int((rights_score + engagement) / 2) + production_bonus - gate_penalty)
    scores = {
        "ad_revenue": min(100, base + (8 if fields["platform"].startswith("youtube") else 0)),
        "sponsorship": min(100, base + (10 if any(term in text for term in ["founder", "business", "tools", "finance", "health"]) else 0)),
        "affiliate": min(100, base + (12 if any(term in text for term in ["tools", "software", "gear", "workflow", "automation"]) else 0)),
        "lead_gen": min(100, base + (14 if any(term in text for term in ["signup", "newsletter", "consult", "download", "lead"]) else 0)),
        "product_service": min(100, base + (10 if any(term in text for term in ["service", "product", "system", "framework"]) else 0)),
        "ip_library": min(100, base + (8 if any(term in text for term in ["framework", "system", "series", "repeat"]) else 0)),
    }
    return {
        "route_scores": scores,
        "best_routes": sorted(scores, key=scores.get, reverse=True)[:3],
        "monetization_guaranteed": False,
        "revenue_guaranteed": False,
    }


def generate_metadata_pack(fields: dict[str, Any]) -> dict[str, Any]:
    title = _clean(fields["title_options"][0]) if fields["title_options"] else f"Fix {fields['topic']}"
    tags = _keyword_tags(fields)
    cta = fields["cta_variants"][0] if fields["cta_variants"] else f"Save this before your next {fields['topic']} decision."
    return {
        "title": title[:90],
        "description": f"A practical breakdown for {fields['audience']} on {fields['topic']}. No hype; focus on a clear next step.",
        "tags": tags[:12],
        "hashtags": [f"#{tag.replace(' ', '')}" for tag in tags[:5]],
        "pinned_comment": cta,
        "primary_cta": cta,
        "platform_notes": f"Package for {fields['platform']}; verify captions, rights evidence, and final export before publishing.",
    }


def _keyword_tags(fields: dict[str, Any]) -> list[str]:
    words = _words(" ".join([fields["topic"], fields["audience"], fields["monetization_goal"]]))
    common = {"the", "and", "for", "with", "your", "this", "that", "from", "into"}
    tags = []
    for word in words:
        if len(word) > 2 and word not in common and word not in tags:
            tags.append(word)
    return tags or ["video", "content", "creator"]


def generate_activation_notes(fields: dict[str, Any]) -> dict[str, Any]:
    topic = fields["topic"]
    audience = fields["audience"]
    return {
        "sponsor_categories": [f"Tools used by {audience}", f"Services related to {topic}", "Education or productivity brands"],
        "affiliate_categories": [f"{topic} tools", "workflow templates", "creator/business software"],
        "lead_magnet_ideas": [f"{topic} checklist", f"{topic} mistake audit", "one-page workflow template"],
        "soft_cta": f"Comment 'checklist' if you want the {topic} worksheet.",
        "conversion_notes": "Keep the CTA useful and low-friction; avoid hard selling inside the first video.",
        "conversion_guaranteed": False,
        "sponsorship_guaranteed": False,
        "affiliate_approval_guaranteed": False,
    }


def generate_repurposing_plan(fields: dict[str, Any]) -> list[dict[str, str]]:
    topic = fields["topic"]
    return [
        {"format": "youtube_shorts", "title_angle": f"The biggest {topic} mistake", "cta": "Save for later", "guidance": "Keep under 60s with strong captions."},
        {"format": "instagram_reels", "title_angle": f"Before you try {topic}", "cta": "Share with a friend", "guidance": "Use visual before/after contrast."},
        {"format": "tiktok", "title_angle": f"Nobody tells you this about {topic}", "cta": "Comment for template", "guidance": "Make the hook more conversational."},
        {"format": "longform", "title_angle": f"Full {topic} framework explained", "cta": "Subscribe/download", "guidance": "Expand each retention beat into a chapter."},
        {"format": "carousel_newsletter", "title_angle": f"{topic} checklist", "cta": "Download checklist", "guidance": "Turn scenes into slides or email sections."},
    ]


def readiness_recommendation(route_scores: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    best = max(route_scores["route_scores"].values()) if route_scores["route_scores"] else 0
    gate = fields.get("rights_gate", {}).get("gate", "pass") if isinstance(fields.get("rights_gate"), dict) else "pass"
    if gate == "block":
        status = "not_ready"
    elif best >= 85 and fields.get("production_ready"):
        status = "ready_for_human_review"
    else:
        status = "needs_packaging_improvement"
    return {
        "status": status,
        "reason": "Rights, engagement, production readiness, and monetization route fit were reviewed.",
        "next_actions": _next_actions(status, gate),
    }


def _next_actions(status: str, gate: str) -> list[str]:
    if gate == "block":
        return ["Resolve rights blockers before production or publishing."]
    if status == "ready_for_human_review":
        return ["Run final human review.", "Confirm asset evidence.", "Prepare platform upload manually."]
    return ["Improve CTA and metadata.", "Confirm production handoff readiness.", "Review rights/source evidence."]


def build_monetization_readiness_report(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_monetization_payload(payload)
    if not normalized["is_valid"]:
        return {"schema_version": P44_REPORT_VERSION, "is_valid": False, "validation_errors": normalized["validation_errors"]}
    fields = normalized["fields"]
    route_scores = score_monetization_routes(fields)
    return {
        "schema_version": P44_REPORT_VERSION,
        "is_valid": True,
        "monetization_route_fit": route_scores,
        "metadata_pack": generate_metadata_pack(fields),
        "activation_notes": generate_activation_notes(fields),
        "repurposing_plan": generate_repurposing_plan(fields),
        "compliance_caveats": [
            "Monetization and revenue are not guaranteed.",
            "Final platform policies and eligibility must be checked manually.",
            "Rights/source evidence should be reviewed before upload.",
            "This is not legal, tax, or platform approval advice.",
        ],
        "final_recommendation": readiness_recommendation(route_scores, fields),
        "monetization_guaranteed": False,
        "revenue_guaranteed": False,
        "upload_or_publish_performed": False,
        "platform_api_called": False,
        "live_analytics_used": False,
        "legal_or_tax_advice_given": False,
    }
