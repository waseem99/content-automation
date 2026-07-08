"""Deterministic football CTA/comment-trigger library helpers.

The helpers in this module create reviewable CTA options without scraping
comments, moderating communities, posting to platforms, or approving content.
"""

from __future__ import annotations

from typing import Any, Literal

ContentType = Literal["short", "explainer", "long_form"]

CTA_TYPES = (
    "debate",
    "prediction",
    "loyalty",
    "ranking",
    "controversy",
    "legacy",
    "versus",
)


def _clean(value: str, field_name: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError(f"{field_name} must not be empty")
    return cleaned


def _cta(
    *,
    index: int,
    cta_type: str,
    cta_text: str,
    source_topic: str,
    subject: str,
    content_type: ContentType,
    intent: str,
    comment_trigger: str,
) -> dict[str, Any]:
    return {
        "cta_id": f"cta_{index:02d}",
        "cta_type": cta_type,
        "cta_text": cta_text,
        "source_topic": source_topic,
        "content_type": content_type,
        "focal_subject": subject,
        "intent": intent,
        "comment_trigger": comment_trigger,
        "platform_fit": ["youtube_shorts", "youtube_long_form"],
        "risk_notes": [
            "Requires editorial review before use.",
            "Must avoid unsupported claims, harassment, and inflammatory wording.",
            "Must not bait abuse toward players, teams, fans, or communities.",
            "Must align with the script, title, hook, and source evidence.",
        ],
        "approval_state": "not_approved",
    }


def build_cta_options(topic: str, *, subject: str | None = None, content_type: ContentType = "short") -> list[dict[str, Any]]:
    """Build deterministic CTA/comment-trigger options for football content."""
    if content_type not in {"short", "explainer", "long_form"}:
        raise ValueError("content_type must be 'short', 'explainer', or 'long_form'")

    topic_text = _clean(topic, "topic")
    subject_text = _clean(subject or topic_text, "subject")

    templates = [
        (
            "debate",
            f"Be honest: are fans too harsh on {subject_text}?",
            "Create a balanced argument without attacking either side.",
            "fans defend or challenge the pressure narrative",
        ),
        (
            "prediction",
            f"What happens next for {subject_text}?",
            "Invite future-looking football predictions without fake certainty.",
            "viewers predict the next tournament or career moment",
        ),
        (
            "loyalty",
            f"{subject_text} fans, are you still backing this story?",
            "Activate fan identity while keeping the wording respectful.",
            "supporters respond from loyalty or memory",
        ),
        (
            "ranking",
            f"Rank {subject_text} by pressure, not talent.",
            "Invite comparison based on a specific dimension.",
            "viewers explain their ranking logic",
        ),
        (
            "controversy",
            f"Is the conversation around {subject_text} fair or exaggerated?",
            "Create a safe controversy frame without unsupported scandal.",
            "viewers debate media and fan narratives",
        ),
        (
            "legacy",
            f"Does this change how you see {subject_text}'s legacy?",
            "Prompt reflective legacy discussion.",
            "viewers connect the moment to long-term reputation",
        ),
        (
            "versus",
            f"Who carries more pressure than {subject_text} right now?",
            "Open a versus comparison without declaring a false winner.",
            "viewers name rival players, teams, or eras",
        ),
    ]

    return [
        _cta(
            index=index,
            cta_type=cta_type,
            cta_text=cta_text,
            source_topic=topic_text,
            subject=subject_text,
            content_type=content_type,
            intent=intent,
            comment_trigger=comment_trigger,
        )
        for index, (cta_type, cta_text, intent, comment_trigger) in enumerate(templates, start=1)
    ]


def apply_cta_options_to_packaging(package: dict[str, Any], cta_options: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a package copy with CTA options attached to packaging."""
    updated = dict(package)
    packaging = dict(updated.get("packaging", {}))
    packaging["cta_comment_trigger_options"] = list(cta_options)
    packaging["status"] = "generated_pending_review"
    packaging["planned_epic"] = "P25"
    updated["packaging"] = packaging
    return updated
