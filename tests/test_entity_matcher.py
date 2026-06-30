"""Tests for entity matching."""

from pathlib import Path

from src.concepts.loader import load_concept
from src.generator.entity_matcher import (
    assign_clips_to_plan,
    clip_matches_entity,
    image_result_matches_entity,
    resolve_video_entity,
)
from src.generator.models import ExplainerPlan, ExplainerSection, VisualBeat


def test_resolve_video_entity_from_filename():
    concept = load_concept(Path("concepts/four_hyped_players_wc2026.yaml"))
    messi_video = Path("RARE Messi Clips for Editing.mp4")
    haaland_video = Path("HAALAND'S GREATEST GOALS.mp4")

    assert resolve_video_entity(messi_video, concept)[0] == "Lionel Messi"
    assert resolve_video_entity(haaland_video, concept)[0] == "Erling Haaland"


def test_clip_matches_by_source_video_not_wrong_tag():
    messi_clip_wrong_tag = {
        "file": "erling_haaland_clip_01.mp4",
        "entity": "Erling Haaland",
        "source_video": "/data/input/RARE Messi Clips.mp4",
    }
    haaland_clip_wrong_tag = {
        "file": "lionel_messi_clip_01.mp4",
        "entity": "Lionel Messi",
        "source_video": "/data/input/HAALAND GREATEST GOALS.mp4",
    }
    assert clip_matches_entity(messi_clip_wrong_tag, "Lionel Messi")
    assert not clip_matches_entity(messi_clip_wrong_tag, "Erling Haaland")
    assert clip_matches_entity(haaland_clip_wrong_tag, "Erling Haaland")
    assert not clip_matches_entity(haaland_clip_wrong_tag, "Lionel Messi")


def test_image_result_rejects_wrong_player():
    assert not image_result_matches_entity(
        "Virgil van Dijk Netherlands orange jersey", "Kylian Mbappe"
    )
    assert image_result_matches_entity(
        "Kylian Mbappe France goal celebration", "Kylian Mbappe"
    )


def test_assign_clips_corrects_swapped_pool():
    plan = ExplainerPlan(
        concept_id="test",
        title="Test",
        sections=[
            ExplainerSection(
                id="messi",
                section_type="entity_block",
                entity_name="Lionel Messi",
                narration="Messi story",
                beats=[
                    VisualBeat(duration_sec=3, visual_type="clip", clip_file="lionel_messi_clip_01.mp4"),
                ],
            ),
        ],
    )
    pool = {
        "clips": [
            {
                "file": "erling_haaland_clip_01.mp4",
                "entity": "Erling Haaland",
                "source_video": "/input/RARE Messi Clips.mp4",
                "score": 0.9,
            },
            {
                "file": "lionel_messi_clip_01.mp4",
                "entity": "Lionel Messi",
                "source_video": "/input/HAALAND GOALS.mp4",
                "score": 0.8,
            },
        ]
    }
    assign_clips_to_plan(plan, pool)
    assert plan.sections[0].beats[0].clip_file == "erling_haaland_clip_01.mp4"
