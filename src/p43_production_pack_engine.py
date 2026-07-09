"""P43 production brief and storyboard pack engine.

This module converts a P40-style video package, with optional P41/P42 analysis,
into a practical handoff pack for editors, designers, animators, and producers.
It generates storyboard frames, shot list, VO/caption timing, asset checklist,
thumbnail directions, review gates, and production notes.

It does not render video, download assets, upload, publish, call external APIs,
or guarantee performance.
"""

from __future__ import annotations

import re
from typing import Any

P43_PACK_VERSION = "p43.production_handoff_pack.v1"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _words(text: str) -> list[str]:
    return re.findall(r"\b\w+[\w'-]*\b", text)


def normalize_production_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a P40/P41/P42 bundle into production-handoff fields."""

    p40 = payload.get("video_package", payload)
    p41 = payload.get("rights_report", {})
    p42 = payload.get("engagement_scorecard", {})
    brief = p40.get("brief", {}) if isinstance(p40.get("brief"), dict) else {}
    production_brief = p40.get("production_brief", {}) if isinstance(p40.get("production_brief"), dict) else {}
    fields = {
        "platform": brief.get("platform") or p40.get("platform") or "unknown",
        "duration_seconds": int(brief.get("duration_seconds") or p40.get("duration_seconds") or 45),
        "topic": brief.get("topic") or p40.get("topic") or "video topic",
        "audience": brief.get("audience") or p40.get("audience") or "target audience",
        "hook": _clean(p40.get("hook")),
        "script": _clean(p40.get("script")),
        "title_options": _as_list(p40.get("title_options")),
        "retention_beats": _as_list(p40.get("retention_beats")),
        "scene_plan": _as_list(p40.get("scene_plan")),
        "asset_requirements": _as_list(p40.get("asset_requirements")),
        "production_brief": production_brief,
        "rights_gate": p41.get("publish_gate", {}),
        "rights_manifest": _as_list(p41.get("asset_source_manifest")),
        "engagement_notes": p42.get("improvement_plan", []),
        "alternate_hooks": _as_list(p42.get("alternate_hooks")),
        "cta_variants": _as_list(p42.get("cta_variants")),
    }
    errors = []
    if not fields["script"]:
        errors.append("missing_script")
    if not fields["scene_plan"]:
        errors.append("missing_scene_plan")
    return {"is_valid": not errors, "validation_errors": errors, "fields": fields}


def _time_range(scene: dict[str, Any], index: int, duration: int, total: int) -> str:
    if scene.get("time_range"):
        return str(scene["time_range"])
    start = int((index - 1) * duration / max(total, 1))
    end = int(index * duration / max(total, 1))
    return f"{start}-{end}s"


def _beat_for_scene(fields: dict[str, Any], index: int) -> str:
    beats = fields["retention_beats"]
    if index - 1 < len(beats) and isinstance(beats[index - 1], dict):
        return _clean(beats[index - 1].get("beat")) or "story"
    return "story"


def generate_storyboard_frames(fields: dict[str, Any]) -> list[dict[str, Any]]:
    scenes = [scene for scene in fields["scene_plan"] if isinstance(scene, dict)]
    frames = []
    for idx, scene in enumerate(scenes, start=1):
        beat = _clean(scene.get("beat")) or _beat_for_scene(fields, idx)
        visual = _clean(scene.get("visual_direction")) or "Original safe visual supporting the script."
        frames.append({
            "frame_number": idx,
            "time_range": _time_range(scene, idx, fields["duration_seconds"], len(scenes)),
            "beat": beat,
            "visual_direction": visual,
            "on_screen_text": _frame_text(beat, fields),
            "motion_note": _motion_note(beat),
            "production_risk_note": "Use owned/licensed visuals only; avoid third-party clips unless cleared.",
        })
    return frames


def _frame_text(beat: str, fields: dict[str, Any]) -> str:
    if "hook" in beat:
        return fields["hook"][:90]
    if "cta" in beat:
        return fields["cta_variants"][0] if fields["cta_variants"] else f"Save this before your next {fields['topic']} decision."
    if "proof" in beat:
        return "Proof, not hype."
    if "framework" in beat:
        return "3-step framework"
    return fields["topic"]


def _motion_note(beat: str) -> str:
    if "hook" in beat:
        return "Fast cold open, bold caption pop, no intro delay."
    if "cta" in beat:
        return "Hold final frame long enough to read and save."
    if "proof" in beat:
        return "Use before/after contrast and subtle zoom."
    return "Keep cuts tight; one idea per frame."


def generate_shot_list(frames: list[dict[str, Any]], fields: dict[str, Any]) -> list[dict[str, Any]]:
    shots = []
    for frame in frames:
        shots.append({
            "shot_id": f"S{frame['frame_number']:02d}",
            "frame_number": frame["frame_number"],
            "purpose": frame["beat"],
            "framing": "Vertical 9:16, safe margins for captions, subject/graphic centered.",
            "transition": "Cut on beat; use motion blur only if it improves clarity.",
            "caption_style": "Large mobile-first captions; emphasize 1-3 key words.",
            "asset_need": _asset_need(frame["beat"], fields),
            "editor_note": frame["motion_note"],
        })
    return shots


def _asset_need(beat: str, fields: dict[str, Any]) -> str:
    if "hook" in beat:
        return "Bold type card or owned hero visual."
    if "proof" in beat:
        return "Owned example, licensed stock, or original animation."
    if "cta" in beat:
        return "Clean end card with handle/CTA placeholder."
    return "Owned graphics, icons, captions, and licensed music bed."


def generate_voiceover_caption_map(frames: list[dict[str, Any]], fields: dict[str, Any]) -> list[dict[str, Any]]:
    words = _words(fields["script"])
    total = max(len(frames), 1)
    chunk_size = max(1, int(len(words) / total))
    mapping = []
    for idx, frame in enumerate(frames):
        start = idx * chunk_size
        end = len(words) if idx == total - 1 else min(len(words), (idx + 1) * chunk_size)
        segment = " ".join(words[start:end]).strip()
        caption_words = segment.split()[:9]
        mapping.append({
            "frame_number": frame["frame_number"],
            "time_range": frame["time_range"],
            "voiceover_segment": segment,
            "caption_text": " ".join(caption_words),
            "emphasis_words": caption_words[:3],
        })
    return mapping


def generate_thumbnail_directions(fields: dict[str, Any]) -> dict[str, Any]:
    title = fields["title_options"][0] if fields["title_options"] else f"Fix {fields['topic']}"
    return {
        "cover_text": title[:58],
        "composition": "One bold visual, one short promise, high contrast, no clutter.",
        "visual_contrast": "Before/after or wrong/right split-screen works best.",
        "emotional_cue": "Curiosity plus practical payoff.",
        "safe_asset_notes": "Avoid logos, copyrighted characters, celebrity likeness, and unlicensed screenshots.",
    }


def generate_asset_checklist(fields: dict[str, Any]) -> list[dict[str, Any]]:
    base = [
        ("voiceover", "Original narration or licensed synthetic voice."),
        ("music", "Licensed/royalty-free track with evidence."),
        ("footage", "Owned footage, licensed stock, or original animation."),
        ("graphics", "Owned graphics/icons/templates with editable source."),
        ("captions", "Mobile-first captions with spelling review."),
        ("font", "Commercial/open-source/system font with license noted."),
        ("thumbnail", "Original cover visual and text treatment."),
        ("source_evidence", "Store license/source notes before publish."),
    ]
    return [{"asset_category": category, "requirement": requirement, "status": "needed"} for category, requirement in base]


def build_production_handoff_pack(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_production_payload(payload)
    if not normalized["is_valid"]:
        return {"schema_version": P43_PACK_VERSION, "is_valid": False, "validation_errors": normalized["validation_errors"]}
    fields = normalized["fields"]
    frames = generate_storyboard_frames(fields)
    shots = generate_shot_list(frames, fields)
    timing = generate_voiceover_caption_map(frames, fields)
    return {
        "schema_version": P43_PACK_VERSION,
        "is_valid": True,
        "production_brief": {
            "platform": fields["platform"],
            "duration_seconds": fields["duration_seconds"],
            "topic": fields["topic"],
            "audience": fields["audience"],
            "objective": fields["production_brief"].get("summary", f"Produce a video about {fields['topic']} for {fields['audience']}.") if isinstance(fields["production_brief"], dict) else f"Produce a video about {fields['topic']}.",
            "review_gates": _review_gates(fields),
        },
        "storyboard_frames": frames,
        "shot_list": shots,
        "voiceover_caption_timing": timing,
        "asset_checklist": generate_asset_checklist(fields),
        "thumbnail_directions": generate_thumbnail_directions(fields),
        "editor_instructions": [
            "Keep the first cut extremely tight; no slow intro.",
            "Prioritize clarity over decorative effects.",
            "Use owned/licensed assets only and keep source evidence.",
            "Export in platform-safe vertical format unless brief says otherwise.",
        ],
        "handoff_ready": True,
        "rendering_performed": False,
        "external_calls_performed": False,
        "upload_or_publish_performed": False,
        "performance_guaranteed": False,
    }


def _review_gates(fields: dict[str, Any]) -> list[str]:
    gates = ["creative review", "rights/source review", "caption QA", "final export QA"]
    rights_gate = fields.get("rights_gate", {})
    if isinstance(rights_gate, dict) and rights_gate.get("gate") in {"revise", "block"}:
        gates.insert(0, f"resolve rights gate: {rights_gate.get('gate')}")
    return gates
