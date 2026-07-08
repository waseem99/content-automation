"""Deterministic retention score report helpers.

The helpers in this module create review-oriented ``retention_score.json``
reports without YouTube analytics, A/B testing, or external scoring services.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

ContentType = Literal["short", "explainer", "long_form"]
RiskLabel = Literal["low", "medium", "high"]

REPORT_SCHEMA_VERSION = "p25.retention_score.v1"


def _clean(value: str, field_name: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _bounded_score(value: int) -> int:
    return max(0, min(10, value))


def _risk_from_score(score: int) -> RiskLabel:
    if score >= 7:
        return "low"
    if score >= 5:
        return "medium"
    return "high"


def _score_text_specificity(text: str, *, subject: str) -> int:
    score = 4
    lowered = text.lower()
    if subject.lower() in lowered:
        score += 2
    if any(term in lowered for term in ["world cup", "record", "tackle", "goal", "legacy", "pressure", "moment"]):
        score += 2
    if "?" in text:
        score += 1
    if len(text.split()) <= 12:
        score += 1
    return _bounded_score(score)


def build_retention_score_report(
    *,
    package_id: str,
    content_type: ContentType,
    topic: str,
    hook_text: str,
    cta_text: str,
    subject: str | None = None,
    has_midpoint_reset: bool = False,
    has_visual_concepts: bool = False,
) -> dict[str, Any]:
    """Build a deterministic retention score report for operator review."""
    if content_type not in {"short", "explainer", "long_form"}:
        raise ValueError("content_type must be 'short', 'explainer', or 'long_form'")

    topic_text = _clean(topic, "topic")
    hook = _clean(hook_text, "hook_text")
    cta = _clean(cta_text, "cta_text")
    subject_text = _clean(subject or topic_text, "subject")

    hook_score = _score_text_specificity(hook, subject=subject_text)
    first_1s_thumb_stop_score = _bounded_score(hook_score + (1 if has_visual_concepts else -1))
    first_3s_clarity_score = _bounded_score(hook_score)
    first_8s_retention_lock_score = _bounded_score(hook_score + (1 if any(term in hook.lower() for term in ["why", "how", "what", "changed"]) else 0))
    curiosity_gap_score = _bounded_score(5 + (2 if "?" in hook or "why" in hook.lower() or "what" in hook.lower() else 0))
    visual_pacing_score = 7 if has_visual_concepts else 5
    midpoint_reset_score = 8 if has_midpoint_reset else 4
    cta_strength_score = _score_text_specificity(cta, subject=subject_text)

    average_core_score = round(
        (
            hook_score
            + first_1s_thumb_stop_score
            + first_3s_clarity_score
            + first_8s_retention_lock_score
            + curiosity_gap_score
            + visual_pacing_score
            + midpoint_reset_score
            + cta_strength_score
        )
        / 8,
        2,
    )

    recommended_fixes: list[str] = []
    if hook_score < 7:
        recommended_fixes.append("Open with a more specific football moment, player, or consequence.")
    if first_1s_thumb_stop_score < 7:
        recommended_fixes.append("Add a stronger first-frame visual interruption or high-contrast caption.")
    if midpoint_reset_score < 7:
        recommended_fixes.append("Add a midpoint reset such as a stat card, comparison, timeline jump, or 'but then' turn.")
    if cta_strength_score < 7:
        recommended_fixes.append("Replace the ending with a debate, prediction, ranking, loyalty, legacy, or versus question.")
    if not recommended_fixes:
        recommended_fixes.append("Review for factual support, rights safety, and editorial alignment before use.")

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "package_id": package_id,
        "content_type": content_type,
        "source_topic": topic_text,
        "hook_text": hook,
        "cta_text": cta,
        "hook_score": hook_score,
        "first_1s_thumb_stop_score": first_1s_thumb_stop_score,
        "first_3s_clarity_score": first_3s_clarity_score,
        "first_8s_retention_lock_score": first_8s_retention_lock_score,
        "curiosity_gap_score": curiosity_gap_score,
        "visual_pacing_score": visual_pacing_score,
        "midpoint_reset_score": midpoint_reset_score,
        "cta_strength_score": cta_strength_score,
        "average_core_score": average_core_score,
        "dead_air_risk": _risk_from_score(visual_pacing_score),
        "genericness_risk": _risk_from_score(hook_score),
        "recommended_fixes": recommended_fixes,
        "status": "generated_pending_review",
        "approval_state": "not_approved",
        "planned_epic": "P25",
        "notes": [
            "Deterministic placeholder report only.",
            "Not based on YouTube Analytics, A/B testing, or live viewer data.",
            "Does not approve publishing, monetization, rights, or editorial status.",
        ],
    }


def apply_retention_score_to_package(package: dict[str, Any], *, report_path: str, report: dict[str, Any]) -> dict[str, Any]:
    """Return a package copy with retention fields linked to a generated report."""
    updated = dict(package)
    retention = dict(updated.get("retention", {}))
    retention.update(
        {
            "retention_score_path": report_path,
            "hook_score": report["hook_score"],
            "first_three_seconds_score": report["first_3s_clarity_score"],
            "midpoint_reset_score": report["midpoint_reset_score"],
            "cta_strength_score": report["cta_strength_score"],
            "dead_air_risk": report["dead_air_risk"],
            "genericness_risk": report["genericness_risk"],
            "recommended_fixes": list(report["recommended_fixes"]),
            "status": "generated_pending_review",
            "planned_epic": "P25",
        }
    )
    updated["retention"] = retention
    return updated


def write_retention_score_report(output_path: Path, report: dict[str, Any]) -> Path:
    """Write a deterministic retention score report to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path
