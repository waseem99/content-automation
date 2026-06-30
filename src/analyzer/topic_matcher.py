"""Topic keyword extraction and transcript scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass

FOOTBALL_SYNONYMS: dict[str, list[str]] = {
    "injury": ["injury", "injured", "hurt", "pain", "stretcher", "down", "collapse", "broken", "fracture"],
    "goal": ["goal", "scores", "scored", "net", "finish", "strike", "header"],
    "comeback": ["comeback", "return", "back", "recovery", "rehab", "fit again"],
    "shock": ["shock", "stunned", "silence", "gasps", "oh no", "devastating"],
    "foul": ["foul", "tackle", "challenge", "collision", "clash"],
    "save": ["save", "keeper", "goalkeeper", "denied", "block"],
    "celebration": ["celebration", "celebrates", "cheers", "roar", "crowd"],
    "analysis": ["analysis", "replay", "look at", "incident", "moment"],
    "world": ["world", "cup", "fifa", "tournament", "knockout"],
    "match": ["match", "game", "fixture", "final", "semifinal", "quarter"],
}


@dataclass
class ScoredSegment:
    start: float
    end: float
    text: str
    topic_score: float
    label: str


def build_keywords(topic: str) -> list[str]:
    topic_lower = topic.lower()
    keywords: set[str] = set()

    tokens = re.findall(r"[a-z0-9']+", topic_lower)
    keywords.update(tokens)

    for key, synonyms in FOOTBALL_SYNONYMS.items():
        if key in topic_lower or any(s in topic_lower for s in synonyms):
            keywords.update(synonyms)

    proper_names = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", topic)
    for name in proper_names:
        keywords.add(name.lower())
        keywords.update(name.lower().split())

    return sorted(k for k in keywords if len(k) > 2)


def _label_from_text(text: str) -> str:
    text_lower = text.lower()
    for label, words in FOOTBALL_SYNONYMS.items():
        if any(word in text_lower for word in words):
            return label
    return "moment"


def score_transcript_segments(
    segments: list,
    topic: str,
) -> list[ScoredSegment]:
    keywords = build_keywords(topic)
    if not keywords:
        return []

    scored: list[ScoredSegment] = []
    for segment in segments:
        text_lower = segment.text.lower()
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits == 0:
            continue
        topic_score = min(1.0, hits / max(1, min(3, len(keywords))))
        scored.append(
            ScoredSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text,
                topic_score=topic_score,
                label=_label_from_text(segment.text),
            )
        )
    return scored
