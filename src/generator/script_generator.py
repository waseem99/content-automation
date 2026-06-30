"""Generate narration script and image search queries via OpenAI."""

from __future__ import annotations

import json

from openai import OpenAI

from src.config import Settings
from src.generator.models import ProductionPlan


def _build_prompt(
    topic: str,
    clip_files: list[str],
    clip_labels: dict[str, str],
    match_context: str,
    target_duration: float,
    clip_duration: float,
    image_count: int,
    intro_duration: float,
) -> str:
    image_narration_budget = target_duration - (len(clip_files) * clip_duration) - intro_duration
    per_image_sec = image_narration_budget / image_count

    clip_descriptions = "\n".join(
        f"- {name} ({clip_labels.get(name, 'highlight')})" for name in clip_files
    )

    if len(clip_files) == 1:
        structure = f"""Video structure (strict order, do NOT change):
1. intro segment — punchy hook that names the player/incident (~{intro_duration:.0f}s when spoken, 8-12 words)
2. image segment 1 — SET UP this specific match moment (~{per_image_sec:.0f}s when spoken)
3. clip — {clip_files[0]} — real match footage, NO narration text (empty string)
4. image segment 2 — explain what just happened in the clip (~{per_image_sec:.0f}s when spoken)
5. image segment 3 — aftermath / stakes / what it means (~{per_image_sec:.0f}s when spoken)"""
    else:
        structure = f"""Video structure (strict order, do NOT change):
1. intro segment — punchy hook that names the player/incident (~{intro_duration:.0f}s when spoken, 8-12 words)
2. image segment 1 — SET UP the match (~{per_image_sec:.0f}s when spoken)
3. clip — {clip_files[0]} — real match footage, NO narration text (empty string)
4. image segment 2 — bridge between moments (~{per_image_sec:.0f}s when spoken)
5. clip — {clip_files[1]} — real match footage, NO narration text (empty string)
6. image segment 3 — closing stakes (~{per_image_sec:.0f}s when spoken)"""

    return f"""Write a YouTube Shorts script grounded in THIS specific football match.

Topic: {topic}

REAL MATCH CONTEXT (use these facts — do not invent other players or events):
{match_context}

{structure}

Clips used:
{clip_descriptions}

Narration rules (critical):
- Sound like a real match analyst / sports documentarian, NOT generic hype
- Use ONLY players, teams, and events from the topic and match context above
- NEVER invent famous players not mentioned in the context (e.g. do not mention random stars)
- Intro must hook the viewer immediately — name the player, team, or incident
- Segment 1 (first image) must set up what the viewer is about to see in the clip(s)
- Segment after each clip must react to what happened in that real footage
- Include specific details: team names, player names, physical incident, tension, consequences
- Avoid empty clichés unless tied to a specific fact
- Present tense, confident, factual tone — as if narrating this exact broadcast moment

Image search query rules (for web image search, NOT AI generation):
- Each intro/image segment needs image_search_query: a short Google Images search phrase
- Name the correct player(s) and team from context (e.g. "Neymar Brazil World Cup 2014")
- Describe the scene: injury, celebration, stadium, training, medical staff, etc.
- Avoid words like "getty" or "reuters" — we search Creative Commons / Wikimedia sources
- image_prompt can mirror image_search_query (legacy field)

Technical constraints:
- Total video target: {target_duration} seconds
- Intro segment type is "intro" (not "image"), image_index null, ~{intro_duration:.1f}s
- Each clip segment is exactly {clip_duration} seconds (no narration on clips)
- Exactly {image_count} image segments with narration (image_index 1, 2, 3)
- clip_file values MUST be exactly: {", ".join(clip_files)} in that order for clip segments
- Do NOT mention copyrighted broadcaster names

Return valid JSON only:
{{
  "title": "short title",
  "segments": [
    {{
      "order": 1,
      "type": "intro",
      "image_index": null,
      "narration": "...",
      "image_search_query": "player team event photo",
      "image_prompt": "",
      "clip_file": "",
      "target_duration_sec": {intro_duration:.1f}
    }},
    {{
      "order": 2,
      "type": "image",
      "image_index": 1,
      "narration": "...",
      "image_search_query": "...",
      "image_prompt": "",
      "clip_file": "",
      "target_duration_sec": {per_image_sec:.1f}
    }},
    {{
      "order": 3,
      "type": "clip",
      "image_index": null,
      "narration": "",
      "image_search_query": "",
      "image_prompt": "",
      "clip_file": "{clip_files[0]}",
      "target_duration_sec": {clip_duration}
    }},
    ...
  ]
}}"""


def generate_production_plan(
    topic: str,
    clip_files: list[str],
    clip_labels: dict[str, str],
    match_context: str,
    settings: Settings,
) -> ProductionPlan:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your .env file.")

    client = OpenAI(api_key=settings.openai_api_key)
    prompt = _build_prompt(
        topic=topic,
        clip_files=clip_files,
        clip_labels=clip_labels,
        match_context=match_context,
        target_duration=settings.target_video_duration,
        clip_duration=settings.clip_segment_duration,
        image_count=settings.image_count,
        intro_duration=settings.intro_duration_sec,
    )

    response = client.chat.completions.create(
        model=settings.openai_model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You write factual, match-specific YouTube Shorts scripts for football. "
                    "Ground every line in the provided match context. Never invent players or "
                    "events. Provide web image search queries, not AI art prompts. "
                    "Always return valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
    )

    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    data["topic"] = topic
    data["target_duration_sec"] = settings.target_video_duration
    data["clip_duration_sec"] = settings.clip_segment_duration
    plan = ProductionPlan.model_validate(data)

    clip_segments = sorted(plan.clip_segments(), key=lambda s: s.order)
    for segment, clip_file in zip(clip_segments, clip_files):
        segment.clip_file = clip_file

    return plan
