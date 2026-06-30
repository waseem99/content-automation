"""Match source videos and clips to the correct player/entity."""

from __future__ import annotations

import re
from pathlib import Path

from src.concepts.loader import ConceptDefinition
from src.generator.models import ExplainerPlan, ExplainerSection

# Last-name hints for matching filenames to entities
ENTITY_NAME_HINTS: dict[str, list[str]] = {
    "Lionel Messi": ["messi", "lionel"],
    "Kylian Mbappe": ["mbappe", "mbappé", "kylian"],
    "Lamine Yamal": ["yamal", "lamin", "lamín"],
    "Erling Haaland": ["haaland", "erling"],
}

# When searching for one player, reject images clearly about another star
CROSS_PLAYER_BLOCKLIST: dict[str, list[str]] = {
    "Lionel Messi": ["mbappe", "mbappé", "haaland", "yamal", "van dijk", "kroos", "foden", "ronaldo", "neymar"],
    "Kylian Mbappe": ["messi", "haaland", "yamal", "van dijk", "kroos", "foden", "ronaldo", "neymar"],
    "Lamine Yamal": ["messi", "mbappe", "mbappé", "haaland", "van dijk", "kroos", "foden", "ronaldo"],
    "Erling Haaland": ["messi", "mbappe", "mbappé", "yamal", "van dijk", "kroos", "foden", "ronaldo"],
}


def entity_hints(entity_name: str) -> list[str]:
    if entity_name in ENTITY_NAME_HINTS:
        return ENTITY_NAME_HINTS[entity_name]
    parts = entity_name.lower().split()
    return parts if parts else [entity_name.lower()]


def video_matches_entity(video_path: Path, entity_name: str) -> bool:
    stem = video_path.stem.lower()
    return any(hint in stem for hint in entity_hints(entity_name))


def resolve_video_entity(
    video_path: Path,
    concept: ConceptDefinition,
) -> tuple[str, str] | None:
    """Match a source video file to entity + extraction topic by filename."""
    for section in concept.entity_sections():
        if video_matches_entity(video_path, section.entity_name):
            for topic in concept.extraction.topics:
                topic_lower = topic.lower()
                hints = entity_hints(section.entity_name)
                if any(h in topic_lower for h in hints):
                    return section.entity_name, topic
            return section.entity_name, f"{section.entity_name} World Cup 2026"
    return None


def clip_matches_entity(clip: dict, entity_name: str) -> bool:
    """Match clips by source video filename (truth), not just the entity tag."""
    source = clip.get("source_video") or ""
    if source:
        return video_matches_entity(Path(source), entity_name)
    return clip.get("entity") == entity_name


def image_result_matches_entity(haystack: str, entity_name: str) -> bool:
    """SerpAPI result title/source must mention the target player."""
    text = haystack.lower()
    hints = entity_hints(entity_name)
    if not any(h in text for h in hints):
        return False
    blocked = CROSS_PLAYER_BLOCKLIST.get(entity_name, [])
    for other in blocked:
        if other in text:
            # Allow if the blocked word is part of the target's own name (rare)
            if other in hints:
                continue
            return False
    return True


def comparison_player_entities(concept: ConceptDefinition | None) -> list[str]:
    if concept:
        return [s.entity_name for s in concept.entity_sections()]
    return list(ENTITY_NAME_HINTS.keys())


def assign_clips_to_plan(plan: ExplainerPlan, clip_pool: dict) -> int:
    """
    Force clip beats to use clips from the correct player's source video.
    Returns number of clip assignments corrected.
    """
    clips = clip_pool.get("clips", [])
    corrected = 0

    for section in plan.entity_sections():
        if not section.entity_name:
            continue
        valid_clips = [
            c for c in clips if clip_matches_entity(c, section.entity_name)
        ]
        valid_clips.sort(key=lambda c: c.get("score", 0), reverse=True)

        clip_beats = [b for b in section.beats if b.visual_type == "clip"]
        for beat, clip in zip(clip_beats, valid_clips):
            if beat.clip_file != clip["file"]:
                beat.clip_file = clip["file"]
                corrected += 1
        # Remove clip assignment if no valid clip
        for beat in clip_beats[len(valid_clips) :]:
            if beat.clip_file:
                beat.visual_type = "web_image"
                beat.clip_file = ""
                if not beat.image_search_query:
                    beat.image_search_query = f"{section.entity_name} World Cup 2026"
                corrected += 1

    return corrected
