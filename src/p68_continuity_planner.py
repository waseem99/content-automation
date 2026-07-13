"""P68 original-concept and continuity-aware clip planning.

The planner converts abstract reference mechanics into a new production plan. It
does not copy reference expression, generate media, render, publish, or approve
facts, rights, originality, or creative quality.
"""

from __future__ import annotations

import re
from typing import Any


P68_PLAN_VERSION = "p68.original_continuity_plan.v1"
SHOT_COUNT_RANGE = range(6, 9)
VIDEO_DURATION_RANGE = (25.0, 38.0)
MIN_TRANSITION_HANDLE_SECONDS = 0.5
MAX_SOURCE_SIMILARITY = 0.35


BRAND_DIRECTIONS = {
    "rawr_nation": {
        "format": "premium factual explainer",
        "angles": ["hidden mechanism", "counterintuitive cause", "scale-shift reveal"],
        "tone": "credible, visual, concise, curious",
    },
    "animal_x": {
        "format": "respectful wildlife micro-documentary",
        "angles": ["behavior mystery", "sensory adaptation", "survival trade-off"],
        "tone": "observational, respectful, evidence-led, quietly cinematic",
    },
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def text_similarity(left: str, right: str) -> float:
    left_tokens, right_tokens = set(_tokens(left)), set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return round(len(left_tokens & right_tokens) / len(left_tokens | right_tokens), 4)


def originality_distance(script: str, source_phrases: list[str]) -> dict[str, Any]:
    comparisons = [
        {"source_phrase": phrase, "similarity": text_similarity(script, phrase)}
        for phrase in source_phrases
        if _clean(phrase)
    ]
    highest = max((item["similarity"] for item in comparisons), default=0.0)
    copied_long_phrases = [
        phrase
        for phrase in source_phrases
        if len(_tokens(phrase)) >= 8 and _clean(phrase).lower() in _clean(script).lower()
    ]
    passed = highest <= MAX_SOURCE_SIMILARITY and not copied_long_phrases
    return {
        "max_similarity": highest,
        "threshold": MAX_SOURCE_SIMILARITY,
        "copied_long_phrases": copied_long_phrases,
        "comparisons": comparisons,
        "automated_check": "pass" if passed else "block",
        "human_originality_review_required": True,
    }


def generate_concept_options(
    *,
    topic: str,
    brand_profile: str,
    reusable_mechanics: list[str],
) -> list[dict[str, Any]]:
    if brand_profile not in BRAND_DIRECTIONS:
        raise ValueError(f"Unsupported P68 brand profile: {brand_profile}")
    topic = _clean(topic)
    if not topic:
        raise ValueError("topic is required")
    direction = BRAND_DIRECTIONS[brand_profile]
    mechanics = [_clean(item) for item in reusable_mechanics if _clean(item)]
    concepts = []
    for index, angle in enumerate(direction["angles"], start=1):
        concepts.append(
            {
                "concept_id": f"{brand_profile}-concept-{index}",
                "topic": topic,
                "angle": angle,
                "format": direction["format"],
                "premise": f"Explain {topic} through an original {angle} visual story.",
                "hook_direction": f"Open on a visible consequence of {topic}, then withhold the cause.",
                "payoff_direction": f"Reveal the mechanism behind {topic} with a new visual demonstration.",
                "tone": direction["tone"],
                "reusable_mechanics": mechanics,
                "source_expression_allowed": False,
                "status": "option_pending_human_selection",
            }
        )
    return concepts


def continuity_bible(
    *,
    subject_identity: str,
    environment: str,
    lighting: str,
    color_treatment: str,
    screen_direction: str = "subject movement remains left-to-right",
    camera_language: str = "grounded cinematic movement with motivated reframing",
) -> dict[str, Any]:
    fields = {
        "subject_identity": _clean(subject_identity),
        "environment": _clean(environment),
        "lighting": _clean(lighting),
        "color_treatment": _clean(color_treatment),
        "screen_direction": _clean(screen_direction),
        "camera_language": _clean(camera_language),
    }
    missing = [name for name, value in fields.items() if not value]
    if missing:
        raise ValueError(f"Missing continuity bible fields: {', '.join(missing)}")
    return {
        **fields,
        "identity_lock": "Preserve defining features, anatomy, wardrobe, proportions, and scale.",
        "environment_lock": "Preserve geography, background landmarks, weather, and time of day.",
        "audio_ambience_lock": "Use one continuous ambience bed unless the story motivates a change.",
        "human_review_required": True,
    }


def _transition(index: int) -> dict[str, str]:
    if index == 0:
        return {"strategy": "cold_open", "audio_bridge": "narration starts on first visible action"}
    strategies = ("action_cut", "match_cut", "direct_cut", "j_cut", "l_cut")
    strategy = strategies[(index - 1) % len(strategies)]
    return {
        "strategy": strategy,
        "audio_bridge": "carry narration, ambience, or motivated SFX across the cut",
    }


def build_shot_plan(
    *,
    script_segments: list[dict[str, Any]],
    bible: dict[str, Any],
) -> list[dict[str, Any]]:
    if len(script_segments) not in SHOT_COUNT_RANGE:
        raise ValueError("P68 plans require 6–8 script/shot segments")
    shots = []
    cursor = 0.0
    for index, segment in enumerate(script_segments):
        duration = float(segment.get("duration_seconds") or 0)
        if duration <= 0:
            raise ValueError(f"Shot {index + 1} duration must be positive")
        action = _clean(segment.get("visual_action"))
        narration = _clean(segment.get("narration"))
        if not action or not narration:
            raise ValueError(f"Shot {index + 1} requires narration and visual_action")
        transition = _transition(index)
        entry_action = _clean(segment.get("entry_action") or f"Continue from shot {index}'s exit pose")
        exit_action = _clean(segment.get("exit_action") or "End on a readable action pose")
        camera = _clean(segment.get("camera") or bible["camera_language"])
        prompt = (
            f"Original vertical cinematic clip. {action}. Subject lock: {bible['subject_identity']}. "
            f"Environment lock: {bible['environment']}. Lighting: {bible['lighting']}. "
            f"Color: {bible['color_treatment']}. Camera: {camera}. Entry: {entry_action}. "
            f"Exit: {exit_action}. Screen direction: {bible['screen_direction']}. "
            "Leave clean motion handles at both ends; no embedded text."
        )
        shots.append(
            {
                "shot_id": f"S{index + 1:02d}",
                "story_stage": _clean(segment.get("story_stage") or "story"),
                "start_seconds": round(cursor, 3),
                "end_seconds": round(cursor + duration, 3),
                "duration_seconds": duration,
                "narration": narration,
                "caption": _clean(segment.get("caption") or narration),
                "visual_action": action,
                "camera": camera,
                "entry_action": entry_action,
                "exit_action": exit_action,
                "screen_direction": bible["screen_direction"],
                "transition_in": transition,
                "transition_handle_seconds": max(
                    MIN_TRANSITION_HANDLE_SECONDS,
                    float(segment.get("transition_handle_seconds") or 0),
                ),
                "ambience": _clean(segment.get("ambience") or bible["audio_ambience_lock"]),
                "sfx": _clean(segment.get("sfx") or "story-motivated subtle accent"),
                "clip_prompt": prompt,
                "negative_prompt": (
                    "identity drift, anatomy change, wardrobe change, background jump, lighting flip, "
                    "reversed screen direction, duplicate subject, watermark, logo, embedded captions"
                ),
                "clip_status": "awaiting_generated_or_approved_clip",
                "human_review_required": True,
            }
        )
        cursor += duration
    return shots


def validate_continuity_plan(plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    shots = plan.get("shots") or []
    duration = sum(float(shot.get("duration_seconds") or 0) for shot in shots)
    if len(shots) not in SHOT_COUNT_RANGE:
        errors.append("shot_count_must_be_6_to_8")
    if not VIDEO_DURATION_RANGE[0] <= duration <= VIDEO_DURATION_RANGE[1]:
        errors.append("duration_must_be_25_to_38_seconds")
    for shot in shots:
        if float(shot.get("transition_handle_seconds") or 0) < MIN_TRANSITION_HANDLE_SECONDS:
            errors.append(f"{shot.get('shot_id')}:missing_transition_handle")
        for field in ("entry_action", "exit_action", "screen_direction", "camera", "ambience"):
            if not _clean(shot.get(field)):
                errors.append(f"{shot.get('shot_id')}:{field}_missing")
    if plan.get("originality_distance", {}).get("automated_check") != "pass":
        errors.append("originality_distance_blocked")
    if not plan.get("factual_notes"):
        errors.append("factual_notes_required")
    for note in plan.get("factual_notes") or []:
        if not _clean(note.get("claim")) or not _clean(note.get("source_url")):
            errors.append("factual_note_claim_and_source_required")
    return sorted(set(errors))


def build_original_content_plan(
    *,
    topic: str,
    brand_profile: str,
    reusable_mechanics: list[str],
    selected_concept_id: str,
    script_segments: list[dict[str, Any]],
    bible: dict[str, Any],
    factual_notes: list[dict[str, str]],
    source_phrases: list[str] | None = None,
) -> dict[str, Any]:
    concepts = generate_concept_options(
        topic=topic,
        brand_profile=brand_profile,
        reusable_mechanics=reusable_mechanics,
    )
    selected = next(
        (item for item in concepts if item["concept_id"] == selected_concept_id),
        None,
    )
    if selected is None:
        raise ValueError("selected_concept_id must identify a generated concept option")
    shots = build_shot_plan(script_segments=script_segments, bible=bible)
    script = " ".join(shot["narration"] for shot in shots)
    plan = {
        "schema_version": P68_PLAN_VERSION,
        "topic": _clean(topic),
        "brand_profile": brand_profile,
        "concept_options": concepts,
        "selected_concept": {**selected, "status": "selected_pending_human_review"},
        "original_script": script,
        "storyboard": [
            {
                "shot_id": shot["shot_id"],
                "story_stage": shot["story_stage"],
                "visual": shot["visual_action"],
                "caption": shot["caption"],
            }
            for shot in shots
        ],
        "continuity_bible": bible,
        "shots": shots,
        "factual_notes": factual_notes,
        "originality_distance": originality_distance(script, source_phrases or []),
        "visual_identity": {
            "format": BRAND_DIRECTIONS[brand_profile]["format"],
            "tone": BRAND_DIRECTIONS[brand_profile]["tone"],
            "continuity_before_style": True,
        },
        "render_allowed": False,
        "publish_allowed": False,
        "human_review_required": True,
        "status": "draft_for_fact_rights_originality_and_creative_review",
    }
    errors = validate_continuity_plan(plan)
    plan["validation"] = {"passed": not errors, "errors": errors}
    return plan
