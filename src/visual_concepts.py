"""Deterministic first-frame and thumbnail concept helpers.

These helpers create reviewable visual concept stubs without rendering images,
calling image-generation APIs, or approving publication assets.
"""

from __future__ import annotations

from typing import Any, Literal

ContentType = Literal["short", "explainer", "long_form"]
ConceptType = Literal["first_frame", "thumbnail"]

VISUAL_PATTERNS = (
    "freeze_frame_punch_in",
    "split_screen_debate",
    "injury_goal_reaction_frame",
    "stat_card_frame",
    "legacy_vs_future_frame",
)


def _clean_text(value: str, field_name: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _concept(
    *,
    index: int,
    concept_type: ConceptType,
    topic: str,
    subject: str,
    content_type: ContentType,
    visual_pattern: str,
    visual_layout: str,
    suggested_text: str,
    emotion: str,
    contrast_idea: str,
) -> dict[str, Any]:
    return {
        "concept_id": f"{concept_type}_{index:02d}",
        "concept_type": concept_type,
        "source_topic": topic,
        "content_type": content_type,
        "platform_fit": ["youtube_shorts"] if concept_type == "first_frame" else ["youtube_long_form", "youtube_shorts"],
        "visual_pattern": visual_pattern,
        "visual_layout": visual_layout,
        "suggested_text": suggested_text,
        "emotion": emotion,
        "focal_subject": subject,
        "contrast_idea": contrast_idea,
        "risk_notes": [
            "Requires editorial review before use.",
            "Must not imply unsupported injury, scandal, or controversy.",
            "Must not use unlicensed player, broadcast, logo, or match imagery without rights review.",
            "Must align with the script, title, hook, and source evidence.",
        ],
        "approval_state": "not_approved",
    }


def build_visual_concepts(topic: str, *, subject: str | None = None, content_type: ContentType = "short") -> dict[str, list[dict[str, Any]]]:
    """Build deterministic first-frame and thumbnail concept stubs."""
    if content_type not in {"short", "explainer", "long_form"}:
        raise ValueError("content_type must be 'short', 'explainer', or 'long_form'")

    topic_text = _clean_text(topic, "topic")
    subject_text = _clean_text(subject or topic_text, "subject")

    first_frame_concepts = [
        _concept(
            index=1,
            concept_type="first_frame",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="freeze_frame_punch_in",
            visual_layout="Full-screen freeze-frame on the key football moment with a tight zoom and high-contrast caption area.",
            suggested_text=f"THIS CHANGED {subject_text.upper()}",
            emotion="shock",
            contrast_idea="moment before impact versus immediate reaction",
        ),
        _concept(
            index=2,
            concept_type="first_frame",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="split_screen_debate",
            visual_layout="Split the frame between the subject and a rival, record, or pressure symbol.",
            suggested_text="WHO HAS MORE PRESSURE?",
            emotion="debate",
            contrast_idea="legacy side versus pressure side",
        ),
        _concept(
            index=3,
            concept_type="first_frame",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="injury_goal_reaction_frame",
            visual_layout="Use a reaction-heavy frame with the subject, teammates, or crowd emotion as the focal point.",
            suggested_text="THE MOMENT EVERYTHING SHIFTED",
            emotion="tension",
            contrast_idea="celebration energy versus sudden silence",
        ),
        _concept(
            index=4,
            concept_type="first_frame",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="stat_card_frame",
            visual_layout="Large stat card beside the subject with simple one-number visual hierarchy.",
            suggested_text="ONE RECORD LEFT?",
            emotion="curiosity",
            contrast_idea="simple number versus emotional player image",
        ),
        _concept(
            index=5,
            concept_type="first_frame",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="legacy_vs_future_frame",
            visual_layout="Two-era frame with past version of the subject on one side and future pressure on the other.",
            suggested_text="LEGACY OR LAST CHANCE?",
            emotion="legacy",
            contrast_idea="past glory versus future question",
        ),
    ]

    thumbnail_concepts = [
        _concept(
            index=1,
            concept_type="thumbnail",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="freeze_frame_punch_in",
            visual_layout="16:9 thumbnail with subject close-up, key moment freeze-frame, and one bold arrow or circle.",
            suggested_text="CHANGED FOREVER",
            emotion="shock",
            contrast_idea="subject emotion against the exact decisive moment",
        ),
        _concept(
            index=2,
            concept_type="thumbnail",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="split_screen_debate",
            visual_layout="16:9 split-screen with subject on left, rival or pressure symbol on right, center tension line.",
            suggested_text="WHO WINS?",
            emotion="debate",
            contrast_idea="fan argument side A versus side B",
        ),
        _concept(
            index=3,
            concept_type="thumbnail",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="injury_goal_reaction_frame",
            visual_layout="16:9 emotional reaction layout with subject/crowd reaction and minimal text.",
            suggested_text="NO ONE EXPECTED THIS",
            emotion="tension",
            contrast_idea="match momentum versus emotional reaction",
        ),
        _concept(
            index=4,
            concept_type="thumbnail",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="stat_card_frame",
            visual_layout="16:9 data-led layout with subject cutout and one oversized stat or record cue.",
            suggested_text="THE RECORD?",
            emotion="curiosity",
            contrast_idea="data certainty versus legacy uncertainty",
        ),
        _concept(
            index=5,
            concept_type="thumbnail",
            topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            visual_pattern="legacy_vs_future_frame",
            visual_layout="16:9 past-versus-future layout using two time periods and a clear central question.",
            suggested_text="LAST CHANCE?",
            emotion="legacy",
            contrast_idea="historic image language versus future tournament pressure",
        ),
    ]

    return {
        "first_frame_options": first_frame_concepts,
        "thumbnail_concepts": thumbnail_concepts,
    }
