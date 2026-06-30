"""Fill missing visual beats on explainer plans (comparison, CTA, etc.)."""

from __future__ import annotations

from src.concepts.loader import ConceptDefinition
from src.generator.models import ExplainerPlan, ExplainerSection, VisualBeat
from src.generator.entity_matcher import ENTITY_NAME_HINTS, comparison_player_entities
from src.generator.prompt_sanitizer import DEFAULT_CINEMATIC_EDIT_PROMPT


def _comparison_beats(section: ExplainerSection, concept: ConceptDefinition | None, duration: float) -> list[VisualBeat]:
    """Four quick cuts — one verified image per player."""
    players = comparison_player_entities(concept)
    if len(players) < 4:
        players = list(ENTITY_NAME_HINTS.keys())
    beat_dur = max(2.5, duration / len(players))
    beats: list[VisualBeat] = []
    for index, player in enumerate(players[:4]):
        beats.append(
            VisualBeat(
                duration_sec=beat_dur,
                visual_type="web_image",
                image_search_query=f"{player} World Cup national team photo",
                cinematic_edit=index == 3,
                cinematic_edit_prompt=DEFAULT_CINEMATIC_EDIT_PROMPT,
                caption_highlight=(section.keyword or "FOUR DIFFERENT PRESSURES") if index == 0 else "",
            )
        )
    return beats


def _cta_web_beat(section: ExplainerSection, duration: float) -> VisualBeat:
    return VisualBeat(
        duration_sec=max(3.0, duration),
        visual_type="web_image",
        image_search_query="World Cup stadium night lights crowd editorial atmosphere",
        cinematic_edit=True,
        cinematic_edit_prompt=DEFAULT_CINEMATIC_EDIT_PROMPT,
        caption_highlight="WHOSE STORY?",
    )


def _comparison_needs_fix(section: ExplainerSection) -> bool:
    if not section.beats:
        return True
    if len(section.beats) < 4:
        return True
    return any(beat.visual_type == "ai_image" for beat in section.beats)


def ensure_plan_beats(plan: ExplainerPlan, concept: ConceptDefinition | None = None) -> bool:
    """
    Add or fix visual beats on narrated sections.
    Comparison/CTA use SerpAPI + cinematic edit (not AI generation with player names).
    Returns True if the plan was modified.
    """
    section_config = {s.id: s for s in concept.sections} if concept else {}
    modified = False

    for section in plan.sections:
        if not section.narration.strip():
            continue

        ref = section_config.get(section.id)
        duration = section.target_duration_sec or (ref.duration_sec if ref else 5.0) or 5.0

        if section.section_type == "comparison":
            if _comparison_needs_fix(section):
                section.beats = _comparison_beats(section, concept, duration)
                modified = True
            continue

        if section.section_type == "cta":
            if not section.beats or any(b.visual_type == "ai_image" for b in section.beats):
                section.beats = [_cta_web_beat(section, duration)]
                modified = True
            continue

        if section.beats:
            continue

        prompt = (
            section.theme
            or section.keyword
            or "World Cup 2026 football editorial illustration"
        )
        query = (
            f"{section.entity_name} World Cup 2026"
            if section.entity_name
            else "World Cup 2026 football editorial"
        )
        section.beats = [
            VisualBeat(
                duration_sec=max(3.0, duration),
                visual_type="web_image",
                image_search_query=query,
                cinematic_edit=True,
                cinematic_edit_prompt=DEFAULT_CINEMATIC_EDIT_PROMPT,
                caption_highlight=section.keyword,
            ),
        ]
        modified = True

    return modified
