"""Tests for concept YAML loader."""

from pathlib import Path

from src.concepts.loader import load_concept


def test_load_four_hyped_players_concept():
    path = Path("concepts/four_hyped_players_wc2026.yaml")
    concept = load_concept(path)
    assert concept.concept_id == "four_hyped_players_wc2026"
    assert concept.target_duration_sec == 120
    assert len(concept.entity_sections()) == 4
    assert concept.entity_sections()[0].entity_name == "Lionel Messi"
    assert concept.extraction.clips_per_video == 4
    assert len(concept.extraction.topics) == 4


def test_narrated_sections_excludes_zero_duration_premise():
    path = Path("concepts/four_hyped_players_wc2026.yaml")
    concept = load_concept(path)
    narrated = concept.narrated_sections()
    assert all(s.duration_sec > 0 for s in narrated)
    assert any(s.id == "hook" for s in narrated)
    assert any(s.id == "cta" for s in narrated)
