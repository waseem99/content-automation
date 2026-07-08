"""Deterministic YouTube title option helpers.

The helper in this module creates structured title-option stubs without
calling AI, YouTube, analytics, or external services. The options are intended
for operator review and future packaging integration, not automatic approval.
"""

from __future__ import annotations

from typing import Any, Literal

ContentType = Literal["short", "explainer", "long_form"]

TITLE_STYLES = (
    "curiosity",
    "debate",
    "nostalgia",
    "record_chase",
    "shock",
    "explainer",
    "legacy",
    "pressure",
    "versus",
    "prediction",
)


def _clean_topic(topic: str) -> str:
    cleaned = " ".join(topic.strip().split())
    if not cleaned:
        raise ValueError("topic must not be empty")
    return cleaned


def build_title_options(topic: str, *, subject: str | None = None, content_type: ContentType = "short") -> list[dict[str, Any]]:
    """Build deterministic, review-required YouTube title options.

    The returned options intentionally include risk notes and do not claim that
    a title is approved, tested, or publish-ready.
    """
    if content_type not in {"short", "explainer", "long_form"}:
        raise ValueError("content_type must be 'short', 'explainer', or 'long_form'")

    topic_text = _clean_topic(topic)
    subject_text = " ".join((subject or topic_text).strip().split())
    if not subject_text:
        subject_text = topic_text

    templates = [
        (
            "curiosity",
            f"The {subject_text} Question Fans Can't Ignore",
            "Open a specific unanswered football question.",
            "curiosity",
        ),
        (
            "debate",
            f"Is {subject_text} Under More Pressure Than Anyone Thinks?",
            "Invite disagreement without making an unsupported claim.",
            "debate",
        ),
        (
            "nostalgia",
            f"Why {subject_text} Still Feels Different",
            "Use memory and emotional connection around the topic.",
            "nostalgia",
        ),
        (
            "record_chase",
            f"The Record {subject_text} Is Really Chasing",
            "Frame the story around a measurable achievement that needs source review.",
            "ambition",
        ),
        (
            "shock",
            f"The Moment That Changed {subject_text}",
            "Promise a concrete moment, not vague drama.",
            "shock",
        ),
        (
            "explainer",
            f"{subject_text} Explained in One Football Story",
            "Make the video format clear and educational.",
            "clarity",
        ),
        (
            "legacy",
            f"What {subject_text} Means for Football Legacy",
            "Position the topic as a legacy question.",
            "legacy",
        ),
        (
            "pressure",
            f"Why the Pressure Around {subject_text} Is Different",
            "Focus on emotional stakes and expectations.",
            "pressure",
        ),
        (
            "versus",
            f"{subject_text}: Talent, Pressure, or Timing?",
            "Create a simple versus-style debate around the angle.",
            "comparison",
        ),
        (
            "prediction",
            f"What Happens Next With {subject_text}?",
            "Invite prediction while avoiding certainty.",
            "prediction",
        ),
    ]

    return [
        {
            "option_id": f"title_{index:02d}",
            "title_text": title,
            "title_style": style,
            "angle": angle,
            "emotional_trigger": emotional_trigger,
            "platform_fit": ["youtube_shorts", "youtube_long_form" if content_type != "short" else "youtube_shorts"],
            "source_topic": topic_text,
            "content_type": content_type,
            "risk_notes": [
                "Requires editorial review before use.",
                "Must not overstate facts beyond the script or source evidence.",
                "Must avoid misleading clickbait and unsupported claims.",
            ],
            "approval_state": "not_approved",
        }
        for index, (style, title, angle, emotional_trigger) in enumerate(templates, start=1)
    ]
