"""Long-form 16:9 concept model helpers for P28.

These helpers define a deterministic planning contract for 6–8 minute YouTube
football videos. They only create and validate planning metadata; they do not
render video, upload to YouTube, ingest analytics, approve rights, or bypass
editorial review.
"""

from __future__ import annotations

from typing import Any

LONG_FORM_SCHEMA_VERSION = "p28.long_form_concept.v1"
LONG_FORM_CONTENT_TYPE = "youtube_long_form"
LONG_FORM_ASPECT_RATIO = "16:9"
TARGET_DURATION_RANGE_MINUTES = (6, 8)

LONG_FORM_SECTION_TYPES = (
    "cold_open",
    "question",
    "context",
    "conflict",
    "turning_point",
    "payoff",
    "comment_trigger",
)

REQUIRED_LONG_FORM_FIELDS = (
    "schema_version",
    "content_type",
    "format",
    "topic",
    "subject",
    "audience",
    "central_question",
    "target_duration_minutes",
    "target_duration_seconds",
    "source_requirements",
    "visual_style",
    "sponsor_slot_markers",
    "chapters",
    "shorts_compatibility",
    "platform_packaging",
    "publish_allowed",
    "review_required",
)

REQUIRED_CHAPTER_FIELDS = (
    "section_type",
    "title",
    "narrative_goal",
    "target_duration_seconds",
    "visual_direction",
    "source_notes",
    "shorts_cutdown_candidate",
)

REQUIRED_SOURCE_FIELDS = (
    "minimum_sources",
    "required_source_types",
    "rights_review_required",
    "factual_review_required",
    "source_attribution_required",
    "unavailable_footage_policy",
)

REQUIRED_VISUAL_STYLE_FIELDS = (
    "aspect_ratio",
    "layout",
    "pacing",
    "visual_system",
    "b_roll_policy",
)


def _clean_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


def _subject_from_topic(topic: str) -> str:
    first_chunk = topic.split(" and ", maxsplit=1)[0]
    first_chunk = first_chunk.split(" vs ", maxsplit=1)[0]
    return first_chunk.strip() or topic


def _build_chapters(topic: str, subject: str) -> list[dict[str, Any]]:
    return [
        {
            "section_type": "cold_open",
            "title": "The moment that makes the viewer stop scrolling",
            "narrative_goal": f"Open with the highest-stakes emotional beat around {subject}, without resolving the story.",
            "target_duration_seconds": 35,
            "visual_direction": "Fast 16:9 montage, scoreboard-style text cards, crowd sound bed, and one unresolved hook line.",
            "source_notes": "Use only rights-reviewed match imagery, licensed stills, or recreated editorial visuals.",
            "shorts_cutdown_candidate": True,
        },
        {
            "section_type": "question",
            "title": "The central question",
            "narrative_goal": f"Frame the main viewer question: what does {topic} reveal about pressure, legacy, or football memory?",
            "target_duration_seconds": 40,
            "visual_direction": "Presenter question card, clean 16:9 lower-third, and timeline setup graphic.",
            "source_notes": "Question must be answerable from verified match reports, official records, and reviewed commentary.",
            "shorts_cutdown_candidate": False,
        },
        {
            "section_type": "context",
            "title": "Why this story mattered before the turning point",
            "narrative_goal": "Give enough background for casual viewers while keeping the football audience engaged.",
            "target_duration_seconds": 85,
            "visual_direction": "Timeline, player/team context cards, map or bracket graphic, and archival-style motion.",
            "source_notes": "Minimum two reliable background sources plus one official or primary reference where possible.",
            "shorts_cutdown_candidate": True,
        },
        {
            "section_type": "conflict",
            "title": "The pressure that changed the stakes",
            "narrative_goal": f"Show the tension, criticism, tactical pressure, or public expectation surrounding {subject}.",
            "target_duration_seconds": 105,
            "visual_direction": "Contrast edits, quote cards from reviewed sources, tactical board moments, and crowd tension.",
            "source_notes": "Claims about pressure, criticism, or performance must be sourced and fact-checked before narration lock.",
            "shorts_cutdown_candidate": True,
        },
        {
            "section_type": "turning_point",
            "title": "The moment the story turned",
            "narrative_goal": "Isolate the decision, incident, match moment, injury, comeback, or performance swing that changed the narrative.",
            "target_duration_seconds": 80,
            "visual_direction": "Slowdown sequence, replay-inspired editorial graphics, and chapter marker transition.",
            "source_notes": "Use timestamped match references or trusted reporting; avoid unsupported tactical or medical claims.",
            "shorts_cutdown_candidate": True,
        },
        {
            "section_type": "payoff",
            "title": "What the story means now",
            "narrative_goal": "Resolve the central question with a clear football takeaway, not a generic motivational ending.",
            "target_duration_seconds": 55,
            "visual_direction": "Clean final montage, legacy card, and restrained music lift after editorial approval.",
            "source_notes": "Final interpretation must separate verified facts from opinion and avoid overclaiming.",
            "shorts_cutdown_candidate": False,
        },
        {
            "section_type": "comment_trigger",
            "title": "The debate to continue below the video",
            "narrative_goal": "End with a specific viewer debate prompt that can also seed Shorts, polls, and community posts.",
            "target_duration_seconds": 20,
            "visual_direction": "End card with one clear debate question and next-video tease area.",
            "source_notes": "Question must not imply unverified facts or encourage harassment of players, clubs, or fans.",
            "shorts_cutdown_candidate": True,
        },
    ]


def build_long_form_concept(
    topic: str,
    *,
    subject: str | None = None,
    audience: str = "Football fans who want story-driven context, tactical clarity, and debate-worthy endings.",
    central_question: str | None = None,
    target_duration_minutes: int = 7,
) -> dict[str, Any]:
    """Build a deterministic 6–8 minute YouTube long-form concept."""

    topic_text = _clean_text(topic, field_name="topic")
    subject_text = _clean_text(subject, field_name="subject") if subject is not None else _subject_from_topic(topic_text)
    audience_text = _clean_text(audience, field_name="audience")

    if not TARGET_DURATION_RANGE_MINUTES[0] <= target_duration_minutes <= TARGET_DURATION_RANGE_MINUTES[1]:
        raise ValueError("target_duration_minutes must be between 6 and 8")

    question_text = (
        _clean_text(central_question, field_name="central_question")
        if central_question is not None
        else f"What does {topic_text} reveal about pressure, legacy, and how football stories are remembered?"
    )
    chapters = _build_chapters(topic_text, subject_text)

    return {
        "schema_version": LONG_FORM_SCHEMA_VERSION,
        "content_type": LONG_FORM_CONTENT_TYPE,
        "format": LONG_FORM_ASPECT_RATIO,
        "topic": topic_text,
        "subject": subject_text,
        "audience": audience_text,
        "central_question": question_text,
        "target_duration_minutes": target_duration_minutes,
        "target_duration_seconds": target_duration_minutes * 60,
        "source_requirements": {
            "minimum_sources": 3,
            "required_source_types": [
                "official match or competition records",
                "reliable match report or archive",
                "rights-reviewed visual source or recreated editorial visual",
            ],
            "rights_review_required": True,
            "factual_review_required": True,
            "source_attribution_required": True,
            "unavailable_footage_policy": "Use recreated editorial visuals, diagrams, or licensed stills when footage is unavailable or unapproved.",
        },
        "visual_style": {
            "aspect_ratio": LONG_FORM_ASPECT_RATIO,
            "layout": "YouTube 16:9 with chapter cards, timeline graphics, lower-thirds, and tactical boards.",
            "pacing": "Documentary explainer pace: fast hook, slower context, sharper conflict, clear payoff.",
            "visual_system": "Football broadcast-inspired graphics with rights-safe recreated visuals.",
            "b_roll_policy": "No unlicensed match footage; use licensed, rights-reviewed, or recreated visual assets only.",
        },
        "sponsor_slot_markers": [
            {
                "slot": "midroll_after_context",
                "after_section_type": "context",
                "target_time_seconds": 160,
                "max_duration_seconds": 30,
                "status": "placeholder_only",
            },
            {
                "slot": "pre_payoff_soft_mention",
                "after_section_type": "turning_point",
                "target_time_seconds": 345,
                "max_duration_seconds": 15,
                "status": "placeholder_only",
            },
        ],
        "chapters": chapters,
        "shorts_compatibility": {
            "compatible_with_shorts_cutdowns": True,
            "recommended_cutdown_sections": [
                chapter["section_type"] for chapter in chapters if chapter["shorts_cutdown_candidate"]
            ],
            "p27_platform_packaging_ready_after_review": True,
            "cutdown_guardrail": "Cutdowns must preserve source, rights, monetization, and editorial review status.",
        },
        "platform_packaging": {
            "youtube_long_form": {
                "title_options_required": True,
                "description_required": True,
                "chapters_required": True,
                "thumbnail_brief_required": True,
                "direct_upload_out_of_scope": True,
            },
            "shorts_funnel": {
                "supported": True,
                "uses_p27_exports_after_review": True,
                "recommended_shorts_count": 3,
            },
        },
        "publish_allowed": False,
        "review_required": True,
    }


def _require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def validate_long_form_concept(concept: dict[str, Any]) -> dict[str, Any]:
    """Validate a long-form concept contract for manual planning readiness."""

    errors: list[str] = []
    warnings: list[str] = []

    _require(set(REQUIRED_LONG_FORM_FIELDS) <= set(concept), errors, "missing required long-form fields")
    _require(concept.get("schema_version") == LONG_FORM_SCHEMA_VERSION, errors, "schema_version mismatch")
    _require(concept.get("content_type") == LONG_FORM_CONTENT_TYPE, errors, "content_type mismatch")
    _require(concept.get("format") == LONG_FORM_ASPECT_RATIO, errors, "format must be 16:9")
    _require(concept.get("publish_allowed") is False, errors, "publish_allowed must remain false")
    _require(concept.get("review_required") is True, errors, "review_required must remain true")

    target_duration_minutes = concept.get("target_duration_minutes")
    _require(
        isinstance(target_duration_minutes, int)
        and TARGET_DURATION_RANGE_MINUTES[0] <= target_duration_minutes <= TARGET_DURATION_RANGE_MINUTES[1],
        errors,
        "target_duration_minutes must be an integer between 6 and 8",
    )
    _require(
        concept.get("target_duration_seconds") == (target_duration_minutes * 60 if isinstance(target_duration_minutes, int) else None),
        errors,
        "target_duration_seconds must match target_duration_minutes",
    )

    for text_field in ("topic", "subject", "audience", "central_question"):
        value = concept.get(text_field)
        _require(isinstance(value, str) and bool(value.strip()), errors, f"{text_field} must be non-empty text")

    source_requirements = concept.get("source_requirements", {})
    if not isinstance(source_requirements, dict):
        source_requirements = {}
    _require(set(REQUIRED_SOURCE_FIELDS) <= set(source_requirements), errors, "missing source requirement fields")
    _require(source_requirements.get("minimum_sources", 0) >= 3, errors, "minimum_sources must be at least 3")
    _require(source_requirements.get("rights_review_required") is True, errors, "rights review must be required")
    _require(source_requirements.get("factual_review_required") is True, errors, "factual review must be required")
    _require(source_requirements.get("source_attribution_required") is True, errors, "source attribution must be required")

    visual_style = concept.get("visual_style", {})
    if not isinstance(visual_style, dict):
        visual_style = {}
    _require(set(REQUIRED_VISUAL_STYLE_FIELDS) <= set(visual_style), errors, "missing visual style fields")
    _require(visual_style.get("aspect_ratio") == LONG_FORM_ASPECT_RATIO, errors, "visual style aspect ratio must be 16:9")

    sponsor_slots = concept.get("sponsor_slot_markers")
    _require(isinstance(sponsor_slots, list) and bool(sponsor_slots), errors, "sponsor_slot_markers must be a non-empty list")
    for slot in sponsor_slots if isinstance(sponsor_slots, list) else []:
        _require(isinstance(slot, dict), errors, "sponsor slot must be an object")
        if isinstance(slot, dict):
            _require(slot.get("status") == "placeholder_only", errors, "sponsor slots must be placeholder_only")
            _require("after_section_type" in slot, errors, "sponsor slot missing after_section_type")

    chapters = concept.get("chapters")
    _require(isinstance(chapters, list) and bool(chapters), errors, "chapters must be a non-empty list")
    chapter_section_types: list[str] = []
    chapter_seconds = 0
    for chapter in chapters if isinstance(chapters, list) else []:
        _require(isinstance(chapter, dict), errors, "chapter must be an object")
        if not isinstance(chapter, dict):
            continue
        _require(set(REQUIRED_CHAPTER_FIELDS) <= set(chapter), errors, "chapter missing required fields")
        section_type = chapter.get("section_type")
        if isinstance(section_type, str):
            chapter_section_types.append(section_type)
        _require(section_type in LONG_FORM_SECTION_TYPES, errors, f"unsupported section_type {section_type}")
        _require(isinstance(chapter.get("target_duration_seconds"), int), errors, "chapter target duration must be integer seconds")
        if isinstance(chapter.get("target_duration_seconds"), int):
            chapter_seconds += chapter["target_duration_seconds"]

    _require(tuple(chapter_section_types) == LONG_FORM_SECTION_TYPES, errors, "chapter section sequence mismatch")
    if isinstance(target_duration_minutes, int) and abs(chapter_seconds - (target_duration_minutes * 60)) > 30:
        warnings.append("chapter duration total differs from target duration by more than 30 seconds")

    shorts_compatibility = concept.get("shorts_compatibility", {})
    if not isinstance(shorts_compatibility, dict):
        shorts_compatibility = {}
    _require(shorts_compatibility.get("compatible_with_shorts_cutdowns") is True, errors, "shorts compatibility must be true")
    _require(shorts_compatibility.get("p27_platform_packaging_ready_after_review") is True, errors, "P27 packaging compatibility must be after review")
    _require(bool(shorts_compatibility.get("recommended_cutdown_sections")), errors, "recommended cutdown sections required")

    platform_packaging = concept.get("platform_packaging", {})
    if not isinstance(platform_packaging, dict):
        platform_packaging = {}
    youtube_packaging = platform_packaging.get("youtube_long_form", {})
    shorts_funnel = platform_packaging.get("shorts_funnel", {})
    _require(isinstance(youtube_packaging, dict), errors, "youtube_long_form packaging must be an object")
    _require(isinstance(shorts_funnel, dict), errors, "shorts_funnel packaging must be an object")
    if isinstance(youtube_packaging, dict):
        _require(youtube_packaging.get("direct_upload_out_of_scope") is True, errors, "direct upload must remain out of scope")
    if isinstance(shorts_funnel, dict):
        _require(shorts_funnel.get("uses_p27_exports_after_review") is True, errors, "shorts funnel must use P27 exports after review")

    return {
        "schema_version": "p28.long_form_concept_validation.v1",
        "is_valid": not errors,
        "publish_allowed": False,
        "review_required": True,
        "required_fields_checked": list(REQUIRED_LONG_FORM_FIELDS),
        "section_types_seen": chapter_section_types,
        "target_duration_seconds": concept.get("target_duration_seconds"),
        "chapter_duration_seconds": chapter_seconds,
        "errors": errors,
        "warnings": warnings,
    }
