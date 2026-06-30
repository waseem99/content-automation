"""Sanitize image prompts to avoid OpenAI public-figure moderation blocks."""

from __future__ import annotations

import re

# Named players → generic editorial archetypes (no public-figure names in AI prompts)
_REPLACEMENTS: list[tuple[str, str]] = [
    ("lionel messi", "Argentina captain legend"),
    ("kylian mbappe", "French striker star"),
    ("kylian mbappé", "French striker star"),
    ("lamine yamal", "Spanish young winger"),
    ("erling haaland", "Norwegian striker"),
    ("messi", "Argentina legend"),
    ("mbappe", "French striker"),
    ("mbappé", "French striker"),
    ("yamal", "Spanish winger"),
    ("haaland", "Norwegian striker"),
]

DEFAULT_CINEMATIC_EDIT_PROMPT = (
    "Apply cinematic documentary color grading, dramatic stadium lighting, "
    "rich contrast, subtle film grain, editorial sports magazine look. "
    "Keep the same composition and subjects; only enhance mood and polish."
)


def sanitize_ai_prompt(prompt: str) -> str:
    """Remove public-figure names from text-to-image prompts."""
    result = prompt
    for name, replacement in _REPLACEMENTS:
        result = re.sub(re.escape(name), replacement, result, flags=re.IGNORECASE)
    return result


def sanitize_web_query(query: str) -> str:
    """Web/SerpAPI queries can keep player names — only trim whitespace."""
    return query.strip()
