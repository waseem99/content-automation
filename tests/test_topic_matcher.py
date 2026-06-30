"""Unit tests for topic keyword matching."""

from src.analyzer.topic_matcher import build_keywords, score_transcript_segments
from src.analyzer.transcriber import TranscriptSegment


def test_build_keywords_includes_injury_synonyms():
    keywords = build_keywords("Neymar injury 2014")
    assert "neymar" in keywords
    assert "injury" in keywords
    assert "stretcher" in keywords


def test_score_transcript_segments_finds_goal_mention():
    segments = [
        TranscriptSegment(start=10.0, end=15.0, text="What a goal from Neymar!"),
    ]
    hits = score_transcript_segments(segments, "Neymar goal")
    assert len(hits) == 1
    assert hits[0].label == "goal"
    assert hits[0].topic_score > 0
