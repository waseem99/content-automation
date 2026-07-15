from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from .models import OriginalBrief, ReferenceFingerprint, ReferenceProject


EXCLUDED_SOURCE_ELEMENTS = [
    "exact script wording",
    "source footage and frame composition",
    "source branding, logos, and watermarks",
    "source music and sound recording",
    "source voice identity",
    "source characters and proprietary artwork",
]


def create_fingerprint(project: ReferenceProject, workspace: Path) -> ReferenceFingerprint:
    if not project.media or not project.analysis:
        raise ValueError("Complete media and analysis are required")
    analysis = project.analysis
    mechanics = [
        f"Use a {analysis.hook.get('hook_type', 'clear')} hook within the first second.",
        f"Target approximately {analysis.pacing.get('visual_changes_per_minute', 0)} visual changes per minute.",
        f"Target approximately {analysis.pacing.get('caption_changes_per_minute', 0)} caption changes per minute.",
        "Create an escalating single-story structure with a distinct payoff.",
        "Keep captions understandable without audio and use purposeful emphasis.",
        "Place the CTA after the narrative payoff rather than before it.",
    ]
    sequence = analysis.visual_language.get("sequence_storytelling") or {}
    observed_mechanics = sequence.get("reusable_mechanics") or []
    if not isinstance(observed_mechanics, list):
        observed_mechanics = []
    mechanics.extend(
        f"Sequence observation for human review: {str(item)[:300]}"
        for item in observed_mechanics[:8]
        if str(item).strip()
    )
    observed_exclusions = sequence.get("source_specific_elements_to_avoid") or []
    if not isinstance(observed_exclusions, list):
        observed_exclusions = []
    exclusions = list(
        dict.fromkeys(
            EXCLUDED_SOURCE_ELEMENTS
            + [str(item)[:300] for item in observed_exclusions[:12] if str(item).strip()]
        )
    )
    timestamps = sorted(
        {
            round(float(value), 3)
            for item in analysis.story_arc
            for value in (item.get("start_seconds", 0), item.get("end_seconds", 0))
        }
    )
    fingerprint = ReferenceFingerprint(
        reference_id=project.reference_id,
        title=project.source.title,
        platform=project.source.platform,
        duration_seconds=project.media.duration_seconds,
        hook=analysis.hook,
        story_arc=analysis.story_arc,
        pacing=analysis.pacing,
        visual_language=analysis.visual_language,
        audio_language=analysis.audio_language,
        objective_scores=analysis.objective_scores,
        reusable_mechanics=mechanics,
        source_specific_elements_to_exclude=exclusions,
        evidence_timestamps=timestamps,
    )
    target = workspace / "exports" / "reference_fingerprint.json"
    target.write_text(fingerprint.model_dump_json(indent=2), encoding="utf-8")
    return fingerprint


def create_original_brief(
    project: ReferenceProject,
    fingerprint: ReferenceFingerprint,
    workspace: Path,
    *,
    brand_id: str,
    topic: str | None = None,
    audience: str = "social video viewers interested in surprising, useful stories",
    duration_seconds: int = 60,
) -> OriginalBrief:
    hook_type = str(fingerprint.hook.get("hook_type") or "immediate curiosity")
    story_stages = [str(item.get("stage")) for item in fingerprint.story_arc]
    brief = OriginalBrief(
        reference_id=project.reference_id,
        brand_id=brand_id,
        duration_seconds=duration_seconds,
        topic=topic or f"Original {brand_id} topic selected during editorial review",
        audience=audience,
        objective_priorities=["engagement", "rights_and_safety", "monetization"],
        hook_formula=f"Establish a new, original {hook_type} hook within 0–1 seconds.",
        pacing_target={
            "visual_changes_per_minute": fingerprint.pacing.get("visual_changes_per_minute"),
            "caption_changes_per_minute": fingerprint.pacing.get("caption_changes_per_minute"),
            "average_shot_seconds": fingerprint.pacing.get("average_shot_seconds"),
            "reference_only_not_a_copy_target": True,
        },
        story_structure=story_stages,
        caption_direction=(
            "Use short, readable phrase captions with one purposeful highlighted word. "
            "Do not copy the reference's wording or exact timing."
        ),
        visual_direction=(
            "Create new scenes, framing, assets, and visual identity appropriate to the selected brand. "
            "Match only the general information density and emotional progression."
        ),
        cta_direction="Place a short brand-appropriate CTA after the story payoff.",
        originality_constraints=EXCLUDED_SOURCE_ELEMENTS
        + [
            "Do not recreate the source scene sequence shot-for-shot.",
            "Do not imply the reference creator endorses or produced the new content.",
            "Run human originality and rights review before rendering.",
        ],
        source_traceability={
            "reference_id": project.reference_id,
            "reference_title": project.source.title,
            "mechanics_used": fingerprint.reusable_mechanics,
            "transformation_note": (
                "Only abstract storytelling and pacing mechanics may be used. "
                "Source-specific creative expression is excluded."
            ),
        },
    )
    target = workspace / "exports" / "original_content_brief.json"
    target.write_text(brief.model_dump_json(indent=2), encoding="utf-8")
    return brief


def _tokens(value: str) -> Counter[str]:
    return Counter(re.findall(r"[a-z0-9]+", value.lower()))


def text_similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = set(left_tokens) & set(right_tokens)
    numerator = sum(left_tokens[token] * right_tokens[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left_tokens.values()))
    right_norm = math.sqrt(sum(value * value for value in right_tokens.values()))
    return round(numerator / max(left_norm * right_norm, 1e-9), 4)


def compare_fingerprints(fingerprints: Iterable[ReferenceFingerprint]) -> dict[str, object]:
    items = list(fingerprints)
    if len(items) < 2:
        raise ValueError("At least two fingerprints are required")
    hook_types = Counter(str(item.hook.get("hook_type")) for item in items)
    story_sequences = [tuple(str(stage.get("stage")) for stage in item.story_arc) for item in items]
    shared_story = list(story_sequences[0]) if all(seq == story_sequences[0] for seq in story_sequences) else []
    average_visual_rate = sum(
        float(item.pacing.get("visual_changes_per_minute") or 0) for item in items
    ) / len(items)
    return {
        "schema_version": "p66.reference_comparison.v1",
        "reference_ids": [item.reference_id for item in items],
        "common_hook_types": hook_types.most_common(),
        "shared_story_sequence": shared_story,
        "average_visual_changes_per_minute": round(average_visual_rate, 2),
        "common_mechanics": sorted(
            set.intersection(*(set(item.reusable_mechanics) for item in items))
        ),
        "source_specific_elements_remain_excluded": True,
    }


def load_fingerprint(path: Path) -> ReferenceFingerprint:
    return ReferenceFingerprint.model_validate_json(path.read_text(encoding="utf-8"))


def save_comparison(workspace: Path, comparison: dict[str, object]) -> Path:
    target = workspace / "exports" / "reference_comparison.json"
    target.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
    return target
