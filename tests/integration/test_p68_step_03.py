from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "reference-engine" / "refintel" / "models.py"
ANALYSIS = ROOT / "reference-engine" / "refintel" / "analysis.py"
REPORT = ROOT / "reference-engine" / "refintel" / "report.py"
DOC = ROOT / "docs" / "operations" / "p68-step-03.md"


def test_p68_step_03_exposes_provenance_confidence_and_review_contract() -> None:
    models = MODELS.read_text(encoding="utf-8")
    analysis = ANALYSIS.read_text(encoding="utf-8")
    report = REPORT.read_text(encoding="utf-8")
    for source in ["measured", "model_observation", "deterministic_fallback"]:
        assert source in models
    for field in [
        "source_type",
        "provider",
        "human_review_required",
        "evidence_summary",
        "fallback_reasons",
    ]:
        assert field in models
    for category in [
        "shot_taxonomy",
        "ocr",
        "emotional_beat",
        "caption_rhythm",
        "audio_cue",
    ]:
        assert category in analysis
    assert "finding.source_type" in report
    assert "finding.provider" in report


def test_p68_step_03_documents_local_first_fallback_and_originality_boundaries() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #714. Closes #717 after the PR merges.",
        "local transcription",
        "OCR/on-screen-text observations",
        "measured edit timing",
        "shot taxonomy",
        "emotional beats",
        "caption rhythm",
        "audio cues",
        "story-stage estimates",
        "It does not invent OCR",
        "must not claim to recognize music",
        "No paid API is required.",
        "No result is permission to publish.",
        "new concept and continuity plan",
        "human-review gates still apply",
    ]:
        assert term in content
