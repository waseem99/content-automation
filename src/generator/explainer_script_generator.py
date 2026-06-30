"""Generate explainer narration and visual beats via OpenAI."""

from __future__ import annotations

import json

from openai import OpenAI

from src.concepts.loader import ConceptDefinition
from src.config import Settings
from src.generator.entity_matcher import assign_clips_to_plan
from src.generator.models import ExplainerPlan, ExplainerSection, VisualBeat


def _clip_catalog_text(clip_pool: dict) -> str:
    lines: list[str] = []
    for clip in clip_pool.get("clips", []):
        lines.append(
            f"- {clip['file']} | entity={clip.get('entity', '')} | "
            f"label={clip.get('label', '')} | score={clip.get('score', 0)} | "
            f"text={clip.get('source_text', '')[:80]}"
        )
    return "\n".join(lines) if lines else "(no clips available)"


def _section_spec_text(concept: ConceptDefinition) -> str:
    lines: list[str] = []
    for section in concept.narrated_sections():
        spec = (
            f"- id={section.id} | type={section.type} | duration_sec={section.duration_sec}"
        )
        if section.entity_name:
            spec += f" | entity={section.entity_name} | theme={section.theme} | keyword={section.keyword}"
        if section.type == "hook":
            spec += f" | beat_style={section.beat_style} | beat_count={section.beat_count}"
        if section.type == "entity_block":
            spec += f" | min_clips={section.min_clips} | max_clips={section.max_clips}"
        lines.append(spec)
    return "\n".join(lines)


def _stats_text(concept: ConceptDefinition) -> str:
    if not concept.stats:
        return "(no stats provided — use general knowledge cautiously)"
    return "\n".join(f"- {key}: {value}" for key, value in concept.stats.items())


def _build_prompt(concept: ConceptDefinition, clip_pool: dict, settings: Settings) -> str:
    hook_beat = settings.hook_beat_sec
    max_still = settings.max_still_beat_sec

    return f"""Write a ~{concept.target_duration_sec}s YouTube explainer script as JSON.

CONCEPT: {concept.title}
CONTEXT:
{concept.context.strip()}

CURRENT STATS (use these facts):
{_stats_text(concept)}

SECTION STRUCTURE (follow exactly — one section per id):
{_section_spec_text(concept)}

AVAILABLE CLIPS (assign clip beats only from this list; clip_file must match exactly):
{_clip_catalog_text(clip_pool)}

NARRATION RULES:
- Hook: tease four storylines WITHOUT naming all players immediately in the first line
- Each entity_block: name reveal → theme → stats → stakes (confident documentary tone)
- Comparison: parallel structure ("X carries… Y carries…")
- CTA: ask a comment question — never say "follow us" or "subscribe"
- Present tense, factual, no empty clichés

VISUAL BEAT RULES (critical for dynamic pacing):
- Each section needs 4–8 beats mixing web_image, ai_image, and clip types
- comparison and cta sections MUST include beats (never empty beats array)
- Hook (beat_style rapid): {hook_beat}–1.5s per beat, mostly ai_image silhouettes/editorial art
- Entity blocks: 2–{max_still}s per beat; include 1–2 clip beats using entity-matched clips
- web_image beats: short SerpAPI search query (player + team + event)
- ai_image beats: stylized editorial illustration prompts — national color palettes, NO official kits/badges, NO photorealistic player likeness copies
- clip beats: narration empty on clip; clip plays with no voiceover overlap
- Beat durations within a section should sum close to target_duration_sec
- caption_highlight: optional uppercase keyword flash (3–6 words max) on key emotional terms

Return valid JSON only:
{{
  "concept_id": "{concept.concept_id}",
  "title": "{concept.title}",
  "target_duration_sec": {concept.target_duration_sec},
  "sections": [
    {{
      "id": "hook",
      "section_type": "hook",
      "entity_name": "",
      "theme": "",
      "keyword": "FOUR DIFFERENT PRESSURES",
      "narration": "full spoken text for this section",
      "target_duration_sec": 10,
      "beats": [
        {{
          "duration_sec": 0.7,
          "visual_type": "ai_image",
          "image_search_query": "",
          "ai_image_prompt": "stylized silhouette...",
          "clip_file": "",
          "caption_highlight": "LEGACY"
        }}
      ]
    }}
  ]
}}"""


def generate_explainer_plan(
    concept: ConceptDefinition,
    clip_pool: dict,
    settings: Settings,
) -> ExplainerPlan:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = _build_prompt(concept, clip_pool, settings)

    response = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You write factual football explainer scripts for YouTube. "
                    "Ground stats in provided data. Return valid JSON with dynamic visual beats. "
                    "Never copy broadcast footage descriptions frame-by-frame."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
    )

    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    plan = ExplainerPlan.model_validate(data)
    _validate_clip_files(plan, clip_pool)
    assign_clips_to_plan(plan, clip_pool)
    return plan


def _validate_clip_files(plan: ExplainerPlan, clip_pool: dict) -> None:
    valid_files = {clip["file"] for clip in clip_pool.get("clips", [])}
    for section in plan.sections:
        for beat in section.beats:
            if beat.visual_type == "clip" and beat.clip_file:
                if beat.clip_file not in valid_files:
                    beat.visual_type = "web_image"
                    beat.clip_file = ""
                    if not beat.image_search_query and section.entity_name:
                        beat.image_search_query = f"{section.entity_name} World Cup 2026"


def merge_concept_sections(plan: ExplainerPlan, concept: ConceptDefinition) -> ExplainerPlan:
    """Fill missing keywords/themes from concept definition."""
    concept_map = {s.id: s for s in concept.sections}
    for section in plan.sections:
        ref = concept_map.get(section.id)
        if not ref:
            continue
        if not section.keyword and ref.keyword:
            section.keyword = ref.keyword
        if not section.theme and ref.theme:
            section.theme = ref.theme
        if not section.entity_name and ref.entity_name:
            section.entity_name = ref.entity_name
        if not section.section_type:
            section.section_type = ref.type
    return plan
