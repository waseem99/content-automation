"""P42 engagement and retention optimization engine.

This module evaluates a P40-style video package for hook strength, pacing,
retention structure, emotional pull, novelty, clarity, share/save potential,
CTA quality, and rewatch potential. It returns diagnostics, variants, and a
scorecard without live analytics, scraping, upload, publishing, or guaranteed
performance claims.
"""

from __future__ import annotations

import json
import re
from typing import Any

P42_SCORECARD_VERSION = "p42.engagement_scorecard.v1"

CURIOSITY_TERMS = ("miss", "wrong", "secret", "before", "truth", "mistake", "nobody", "hidden")
URGENCY_TERMS = ("before", "now", "today", "stop", "avoid", "costing", "wasting")
EMOTION_TERMS = ("fear", "waste", "win", "fail", "simple", "pain", "trust", "result", "growth")
SAVE_TERMS = ("framework", "checklist", "steps", "save", "template", "system", "mistake")
CTA_TERMS = ("save", "follow", "comment", "share", "download", "subscribe", "sign up", "try")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def normalize_engagement_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize P40 package or direct payload for engagement scoring."""

    brief = payload.get("brief", {}) if isinstance(payload.get("brief"), dict) else {}
    fields = {
        "platform": brief.get("platform") or payload.get("platform") or "unknown",
        "duration_seconds": int(brief.get("duration_seconds") or payload.get("duration_seconds") or 45),
        "audience": brief.get("audience") or payload.get("audience") or "general audience",
        "topic": brief.get("topic") or payload.get("topic") or "video topic",
        "titles": payload.get("title_options", payload.get("titles", [])),
        "hook": payload.get("hook", ""),
        "script": payload.get("script", ""),
        "retention_beats": payload.get("retention_beats", []),
        "scene_plan": payload.get("scene_plan", []),
        "production_brief": payload.get("production_brief", {}),
    }
    errors = []
    if not str(fields["hook"]).strip():
        errors.append("missing_hook")
    if not str(fields["script"]).strip():
        errors.append("missing_script")
    return {"is_valid": not errors, "validation_errors": errors, "fields": fields}


def score_hook(fields: dict[str, Any]) -> dict[str, Any]:
    hook = str(fields["hook"])
    audience = str(fields["audience"]).lower()
    hook_lower = hook.lower()
    wc = _word_count(hook)
    diagnostics = {
        "specificity": 85 if fields["topic"].lower() in hook_lower else 65,
        "curiosity_gap": 90 if _contains_any(hook, CURIOSITY_TERMS) else 62,
        "audience_relevance": 84 if any(part in hook_lower for part in audience.split()[:3]) else 70,
        "clarity": 92 if 8 <= wc <= 24 else 72,
        "urgency": 88 if _contains_any(hook, URGENCY_TERMS) else 64,
        "contradiction": 90 if any(term in hook_lower for term in ["not", "wrong", "but", "miss"]) else 66,
    }
    score = int(sum(diagnostics.values()) / len(diagnostics))
    fixes = []
    if diagnostics["specificity"] < 80:
        fixes.append("Name the exact topic or outcome in the first line.")
    if diagnostics["curiosity_gap"] < 80:
        fixes.append("Add a curiosity gap: what viewers are missing, wasting, or getting wrong.")
    if diagnostics["clarity"] < 80:
        fixes.append("Keep the hook between 8 and 24 words for fast comprehension.")
    return {"hook_score": score, "diagnostics": diagnostics, "fixes": fixes}


def estimate_retention_curve(fields: dict[str, Any]) -> dict[str, Any]:
    duration = max(15, int(fields["duration_seconds"]))
    beats = fields.get("retention_beats") or []
    scene_plan = fields.get("scene_plan") or []
    script_wc = _word_count(str(fields["script"]))
    density = script_wc / max(duration, 1)
    beat_count = len(beats)
    scene_count = len(scene_plan)
    pacing_score = 76
    if 1.7 <= density <= 3.4:
        pacing_score += 10
    if beat_count >= 5:
        pacing_score += 8
    if scene_count >= beat_count >= 5:
        pacing_score += 6
    pacing_score = min(100, pacing_score)
    curve = []
    checkpoints = [0, 3, 8, 15, 25, 40, duration]
    checkpoints = sorted(set(item for item in checkpoints if item <= duration))
    if checkpoints[-1] != duration:
        checkpoints.append(duration)
    for index, second in enumerate(checkpoints):
        drop = index * (6 if pacing_score >= 88 else 9)
        curve.append({"second": second, "estimated_retention_pct": max(35, 100 - drop)})
    issues = []
    if beat_count < 5:
        issues.append("Add more explicit retention beats to avoid a flat middle.")
    if density > 3.6:
        issues.append("Script may be too dense for the target duration.")
    if density < 1.3:
        issues.append("Script may feel thin; add proof, contrast, or payoff.")
    return {"pacing_score": pacing_score, "estimated_curve": curve, "issues": issues}


def score_engagement_dimensions(fields: dict[str, Any]) -> dict[str, Any]:
    text = " ".join([_stringify(fields.get("titles")), fields["hook"], fields["script"]]).lower()
    scores = {
        "emotional_pull": 86 if _contains_any(text, EMOTION_TERMS) else 68,
        "novelty": 88 if _contains_any(text, ("wrong", "truth", "hidden", "before")) else 70,
        "clarity": 90 if _word_count(fields["script"]) >= 60 else 74,
        "shareability": 84 if _contains_any(text, ("mistake", "truth", "wrong")) else 66,
        "saveability": 88 if _contains_any(text, SAVE_TERMS) else 65,
        "rewatch_loop": 82 if _contains_any(text, ("next step", "repeat", "system", "loop")) else 62,
        "cta_quality": 86 if _contains_any(text, CTA_TERMS) else 64,
    }
    notes = {name: _note_for_dimension(name, score) for name, score in scores.items()}
    return {"dimension_scores": scores, "notes": notes}


def _note_for_dimension(name: str, score: int) -> str:
    if score >= 85:
        return f"{name} is strong enough for production review."
    return f"Improve {name} with a clearer viewer payoff and stronger wording."


def generate_hook_variants(fields: dict[str, Any]) -> list[str]:
    topic = fields["topic"]
    audience = fields["audience"]
    return [
        f"Most {audience} are using {topic} backwards.",
        f"Before you spend another hour on {topic}, fix this first.",
        f"The biggest {topic} mistake is invisible until it costs you results.",
        f"If {topic} feels complicated, this 3-step reset is the shortcut.",
        f"Nobody tells {audience} this part of {topic}.",
    ]


def generate_cta_variants(fields: dict[str, Any]) -> list[str]:
    topic = fields["topic"]
    return [
        f"Save this before your next {topic} decision.",
        f"Comment 'system' if you want the full {topic} checklist.",
        f"Follow for the next practical breakdown on {topic}.",
    ]


def generate_improvement_plan(hook_result: dict[str, Any], retention: dict[str, Any], dimensions: dict[str, Any]) -> list[dict[str, str]]:
    plan = []
    for fix in hook_result["fixes"]:
        plan.append({"priority": "high", "area": "hook", "action": fix})
    for issue in retention["issues"]:
        plan.append({"priority": "high", "area": "retention", "action": issue})
    for name, score in dimensions["dimension_scores"].items():
        if score < 80:
            plan.append({
                "priority": "medium",
                "area": name,
                "action": f"Raise {name} by adding a more specific viewer payoff or visual proof.",
            })
    return plan or [{"priority": "low", "area": "final_polish", "action": "Ready for human creative review."}]


def build_engagement_scorecard(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_engagement_payload(payload)
    if not normalized["is_valid"]:
        return {
            "schema_version": P42_SCORECARD_VERSION,
            "is_valid": False,
            "validation_errors": normalized["validation_errors"],
        }
    fields = normalized["fields"]
    hook_result = score_hook(fields)
    retention = estimate_retention_curve(fields)
    dimensions = score_engagement_dimensions(fields)
    dimension_avg = int(sum(dimensions["dimension_scores"].values()) / len(dimensions["dimension_scores"]))
    overall = int((hook_result["hook_score"] + retention["pacing_score"] + dimension_avg) / 3)
    return {
        "schema_version": P42_SCORECARD_VERSION,
        "is_valid": True,
        "platform": fields["platform"],
        "duration_seconds": fields["duration_seconds"],
        "hook_diagnostics": hook_result,
        "retention_analysis": retention,
        "engagement_dimensions": dimensions,
        "alternate_hooks": generate_hook_variants(fields),
        "cta_variants": generate_cta_variants(fields),
        "improvement_plan": generate_improvement_plan(hook_result, retention, dimensions),
        "overall_engagement_score": overall,
        "performance_guaranteed": False,
        "live_analytics_used": False,
    }
