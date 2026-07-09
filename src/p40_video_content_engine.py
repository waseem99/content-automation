"""P40 core monetizable video content engine.

This module is the first real product layer for the repo. It turns a topic/niche
brief into a deterministic, JSON-serializable video package with creative angle,
titles, hook, script, retention beats, scene plan, asset needs, copyright risk
notes, engagement scoring, monetization readiness scoring, and a production brief.

It does not call external APIs, scrape platforms, download assets, render video,
upload content, or claim guaranteed monetization/legal clearance.
"""

from __future__ import annotations

import re
from typing import Any

P40_PACKAGE_VERSION = "p40.video_content_package.v1"

SUPPORTED_PLATFORMS = {
    "youtube_shorts": {"duration": 45, "beat_seconds": [0, 3, 8, 15, 24, 35, 45], "format": "vertical_short"},
    "tiktok": {"duration": 35, "beat_seconds": [0, 2, 6, 12, 20, 28, 35], "format": "vertical_short"},
    "instagram_reels": {"duration": 40, "beat_seconds": [0, 3, 7, 14, 22, 32, 40], "format": "vertical_short"},
    "youtube_long": {"duration": 480, "beat_seconds": [0, 15, 45, 90, 180, 300, 420, 480], "format": "longform"},
}

DEFAULT_PLATFORM = "youtube_shorts"
DECISION_SAFE = "human_review_required"

RIGHTS_PATTERNS = {
    "copyrighted_character_or_franchise": [
        "marvel", "disney", "pixar", "batman", "superman", "spider-man", "spiderman", "harry potter",
        "star wars", "pokemon", "naruto", "dragon ball", "mickey mouse", "barbie",
    ],
    "celebrity_likeness_or_voice": [
        "as mrbeast", "mrbeast style", "elon musk voice", "taylor swift voice", "celebrity voice", "deepfake",
    ],
    "commercial_music_or_clip": [
        "use this song", "famous song", "movie clip", "netflix clip", "tiktok audio", "copyrighted music",
    ],
    "copied_style_or_premise": [
        "in the style of", "exactly like", "copy the", "remake scene", "shot for shot", "same plot as"],
    "brand_dependency": ["nike", "apple", "tesla", "coca-cola", "netflix", "youtube", "instagram", "tiktok"],
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_clean(item) for item in value if _clean(item)]
    return [_clean(value)] if _clean(value) else []


def normalize_video_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate a video generation brief."""

    platform = _clean(brief.get("platform")).lower().replace(" ", "_") or DEFAULT_PLATFORM
    if platform not in SUPPORTED_PLATFORMS:
        platform = DEFAULT_PLATFORM
    platform_defaults = SUPPORTED_PLATFORMS[platform]
    duration = int(brief.get("duration_seconds") or platform_defaults["duration"])
    duration = max(15, min(duration, 900))
    normalized = {
        "topic": _clean(brief.get("topic") or brief.get("niche")),
        "platform": platform,
        "audience": _clean(brief.get("audience")),
        "tone": _clean(brief.get("tone")) or "smart, fast, cinematic",
        "duration_seconds": duration,
        "monetization_goal": _clean(brief.get("monetization_goal")),
        "content_format": _clean(brief.get("content_format")) or platform_defaults["format"],
        "must_use_points": _as_list(brief.get("must_use_points")),
        "avoid": _as_list(brief.get("avoid")),
        "source_notes": _as_list(brief.get("source_notes")),
    }
    errors = []
    for field in ["topic", "audience", "monetization_goal"]:
        if not normalized[field]:
            errors.append(f"missing_{field}")
    normalized["is_valid"] = not errors
    normalized["validation_errors"] = errors
    return normalized


def generate_concepts(brief: dict[str, Any]) -> list[dict[str, str]]:
    topic = brief["topic"]
    audience = brief["audience"]
    goal = brief["monetization_goal"]
    return [
        {
            "angle_id": "contrarian_truth",
            "angle": f"The uncomfortable truth about {topic}",
            "audience_promise": f"Help {audience} understand what most people miss before they waste time or money.",
            "curiosity_driver": "Challenges a common belief in the first line.",
            "monetization_fit": f"Works for {goal} because it frames the creator as a trusted advisor.",
            "differentiator": "Original explanation, no dependency on third-party characters, music, or clips.",
        },
        {
            "angle_id": "mistake_stack",
            "angle": f"The 3 mistakes that make {topic} fail",
            "audience_promise": f"Give {audience} a practical checklist they can act on immediately.",
            "curiosity_driver": "Keeps viewers watching to discover mistake three and the fix.",
            "monetization_fit": f"Fits {goal} by creating a natural bridge to tools, services, or deeper content.",
            "differentiator": "Uses owned commentary and original framework instead of copied material.",
        },
        {
            "angle_id": "before_after_path",
            "angle": f"Before vs after understanding {topic}",
            "audience_promise": f"Show {audience} a transformation they can visualize clearly.",
            "curiosity_driver": "Creates an open loop between the current pain and improved outcome.",
            "monetization_fit": f"Supports {goal} with clear proof of value and audience intent.",
            "differentiator": "Built around original examples and abstract visuals.",
        },
    ]


def generate_titles(brief: dict[str, Any]) -> list[str]:
    topic = brief["topic"]
    audience = brief["audience"]
    return [
        f"Most People Get {topic} Wrong",
        f"The {topic} Mistake Costing {audience} Results",
        f"I Wish I Knew This About {topic} Earlier",
        f"The Simple {topic} Framework That Actually Works",
        f"Before You Try {topic}, Watch This",
        f"3 Signs Your {topic} Strategy Is Broken",
    ]


def generate_hook(brief: dict[str, Any], concept: dict[str, str]) -> str:
    return f"If you think {brief['topic']} is just about working harder, this is the part most people miss."


def generate_retention_beats(brief: dict[str, Any]) -> list[dict[str, Any]]:
    seconds = SUPPORTED_PLATFORMS[brief["platform"]]["beat_seconds"]
    seconds = [min(item, brief["duration_seconds"]) for item in seconds if item <= brief["duration_seconds"]]
    if seconds[-1] != brief["duration_seconds"]:
        seconds.append(brief["duration_seconds"])
    labels = ["hook", "stakes", "mistake", "framework", "proof", "payoff", "cta"]
    beats = []
    for index, start in enumerate(seconds[:-1]):
        end = seconds[index + 1]
        beats.append({
            "beat": labels[min(index, len(labels) - 1)],
            "start_seconds": start,
            "end_seconds": end,
            "purpose": _beat_purpose(labels[min(index, len(labels) - 1)], brief),
        })
    return beats


def _beat_purpose(label: str, brief: dict[str, Any]) -> str:
    purposes = {
        "hook": "Break the viewer's assumption immediately.",
        "stakes": f"Make {brief['audience']} feel the cost of ignoring the idea.",
        "mistake": "Name the main mistake clearly.",
        "framework": "Give a simple original framework.",
        "proof": "Show a concrete example or visual contrast.",
        "payoff": "Deliver the practical lesson promised by the hook.",
        "cta": f"Invite the viewer toward {brief['monetization_goal']} without sounding spammy.",
    }
    return purposes[label]


def generate_script(brief: dict[str, Any], concept: dict[str, str], hook: str) -> str:
    must_use = " ".join(brief["must_use_points"])
    return " ".join([
        hook,
        f"Most {brief['audience']} focus on the visible part of {brief['topic']}, but the real leverage is the decision system behind it.",
        "Here is the simple framework: spot the wrong assumption, replace it with one measurable action, then test the result before scaling.",
        f"For example, instead of copying what everyone else is doing, build one original proof point around {brief['topic']} and make it easy to understand visually.",
        must_use,
        "That is how you turn attention into trust, and trust into a monetizable audience relationship.",
        f"Save this if your goal is {brief['monetization_goal']}, because the next step is turning the idea into a repeatable content system.",
    ]).strip()


def generate_scene_plan(brief: dict[str, Any], beats: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenes = []
    for idx, beat in enumerate(beats, start=1):
        scenes.append({
            "scene_number": idx,
            "time_range": f"{beat['start_seconds']}-{beat['end_seconds']}s",
            "beat": beat["beat"],
            "visual_direction": _visual_for_beat(beat["beat"], brief),
            "editing_note": "Use fast cuts, caption emphasis, and one clear visual idea per beat.",
        })
    return scenes


def _visual_for_beat(beat: str, brief: dict[str, Any]) -> str:
    visuals = {
        "hook": f"Cold open with bold text: 'You are thinking about {brief['topic']} wrong.'",
        "stakes": "Show split-screen: wasted effort vs focused system.",
        "mistake": "Use simple icons to reveal the main mistake.",
        "framework": "Animate a 3-step original framework on screen.",
        "proof": "Show an abstract before/after example using owned graphics or stock-safe visuals.",
        "payoff": "Zoom into the key takeaway as a clean checklist.",
        "cta": "End with a saved-note style frame and soft CTA.",
    }
    return visuals.get(beat, "Use original abstract visuals, captions, and owned graphics.")


def screen_rights_risks(text: str, avoid: list[str] | None = None) -> dict[str, Any]:
    lowered = text.lower()
    findings = []
    for category, terms in RIGHTS_PATTERNS.items():
        for term in terms:
            if term in lowered:
                findings.append({
                    "category": category,
                    "term": term,
                    "risk": "high" if category != "brand_dependency" else "medium",
                    "safer_alternative": _safer_alternative(category),
                })
    for term in avoid or []:
        if term.lower() in lowered:
            findings.append({"category": "user_avoid_list", "term": term, "risk": "medium", "safer_alternative": "Remove or reframe this reference."})
    high = any(item["risk"] == "high" for item in findings)
    return {
        "risk_level": "high" if high else ("medium" if findings else "low"),
        "findings": findings,
        "human_review": DECISION_SAFE if findings else "optional_review",
        "legal_clearance_claimed": False,
    }


def _safer_alternative(category: str) -> str:
    return {
        "copyrighted_character_or_franchise": "Use an original character, archetype, or generic category instead.",
        "celebrity_likeness_or_voice": "Use an original narrator persona and do not imitate a real person.",
        "commercial_music_or_clip": "Use licensed, royalty-free, or owned audio/visual assets.",
        "copied_style_or_premise": "Describe the desired emotion or structure, not a protected style or scene.",
        "brand_dependency": "Keep brand mentions factual or replace with generic category wording.",
    }.get(category, "Use original owned material.")


def score_package(brief: dict[str, Any], hook: str, script: str, risks: dict[str, Any]) -> dict[str, Any]:
    hook_score = min(100, 55 + (15 if "miss" in hook.lower() else 0) + (10 if len(hook) < 140 else 0))
    clarity_score = 85 if len(script.split()) >= 65 else 70
    curiosity_score = 88 if any(word in hook.lower() for word in ["miss", "wrong", "before"]) else 72
    pacing_score = 90 if brief["duration_seconds"] <= 60 else 78
    rights_score = {"low": 92, "medium": 70, "high": 35}[risks["risk_level"]]
    monetization_score = int((clarity_score + rights_score + 82) / 3)
    engagement_score = int((hook_score + curiosity_score + pacing_score + clarity_score) / 4)
    return {
        "engagement_score": engagement_score,
        "monetization_readiness_score": monetization_score,
        "subscores": {
            "hook_strength": hook_score,
            "clarity": clarity_score,
            "curiosity_gap": curiosity_score,
            "pacing": pacing_score,
            "rights_safety": rights_score,
            "platform_fit": 88,
            "repurposing_fit": 84,
        },
        "improvement_notes": _improvement_notes(engagement_score, monetization_score, risks),
        "monetization_guaranteed": False,
    }


def _improvement_notes(engagement: int, monetization: int, risks: dict[str, Any]) -> list[str]:
    notes = []
    if engagement < 85:
        notes.append("Sharpen the first line with a stronger contradiction or visual surprise.")
    if monetization < 85:
        notes.append("Improve monetization readiness by adding a clearer audience problem and safer asset plan.")
    if risks["risk_level"] != "low":
        notes.append("Resolve rights findings before production or publishing.")
    return notes or ["Package is ready for human creative review and production planning."]


def build_asset_requirements(brief: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"asset": "voiceover", "requirement": "Original narration or licensed voice; no celebrity imitation."},
        {"asset": "music", "requirement": "Royalty-free, owned, or properly licensed background track."},
        {"asset": "visuals", "requirement": "Owned graphics, licensed stock, or original generated visuals with reviewed rights."},
        {"asset": "captions", "requirement": "Burned-in captions optimized for mobile retention."},
        {"asset": "thumbnail_or_cover", "requirement": f"High-contrast promise around {brief['topic']}; avoid third-party IP."},
    ]


def generate_video_package(raw_brief: dict[str, Any]) -> dict[str, Any]:
    brief = normalize_video_brief(raw_brief)
    if not brief["is_valid"]:
        return {"schema_version": P40_PACKAGE_VERSION, "is_valid": False, "validation_errors": brief["validation_errors"], "input": brief}
    concepts = generate_concepts(brief)
    selected = concepts[0]
    titles = generate_titles(brief)
    hook = generate_hook(brief, selected)
    beats = generate_retention_beats(brief)
    script = generate_script(brief, selected, hook)
    scenes = generate_scene_plan(brief, beats)
    risk_text = " ".join([brief["topic"], selected["angle"], hook, script, " ".join(titles), " ".join(brief["source_notes"])])
    risks = screen_rights_risks(risk_text, brief["avoid"])
    scores = score_package(brief, hook, script, risks)
    assets = build_asset_requirements(brief)
    return {
        "schema_version": P40_PACKAGE_VERSION,
        "is_valid": True,
        "brief": brief,
        "positioning": {
            "platform": brief["platform"],
            "content_format": brief["content_format"],
            "audience_promise": selected["audience_promise"],
            "monetization_goal": brief["monetization_goal"],
        },
        "concepts": concepts,
        "selected_concept": selected,
        "title_options": titles,
        "hook": hook,
        "retention_beats": beats,
        "script": script,
        "scene_plan": scenes,
        "asset_requirements": assets,
        "rights_risk": risks,
        "scores": scores,
        "production_brief": {
            "summary": f"Produce a {brief['duration_seconds']}s {brief['platform']} video about {brief['topic']} for {brief['audience']}.",
            "creative_direction": "Original, fast-paced, practical, visually clear, and monetization-safe.",
            "editor_notes": "Use punchy captions, one idea per scene, owned/licensed visuals only, and no third-party clips unless cleared.",
            "review_required_before_publish": True,
        },
    }
