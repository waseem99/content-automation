from __future__ import annotations

from src.p68_continuity_planner import (
    build_original_content_plan,
    continuity_bible,
    generate_concept_options,
    originality_distance,
)


def segments() -> list[dict[str, object]]:
    stages = ["hook", "setup", "mechanism", "escalation", "reveal", "resolution"]
    return [
        {
            "story_stage": stage,
            "duration_seconds": 5,
            "narration": f"Original narration for the {stage} beat number {index}.",
            "visual_action": f"The subject performs a distinct {stage} action in one environment.",
            "entry_action": f"Enter the {stage} beat on continued forward movement.",
            "exit_action": f"Exit the {stage} beat with the subject facing right.",
            "camera": "Slow forward tracking at subject eye level.",
            "ambience": "Continuous soft wind and distant wildlife.",
            "sfx": "Subtle movement accent.",
        }
        for index, stage in enumerate(stages, start=1)
    ]


def bible() -> dict[str, object]:
    return continuity_bible(
        subject_identity="One adult elephant with a small notch in the right ear",
        environment="Dry woodland clearing with one fallen acacia on frame left",
        lighting="Warm dawn light from camera right",
        color_treatment="Natural earth tones with restrained contrast",
    )


def test_generates_three_original_brand_concepts_from_abstract_mechanics() -> None:
    concepts = generate_concept_options(
        topic="elephant ground-vibration communication",
        brand_profile="animal_x",
        reusable_mechanics=["open with visible consequence", "reveal after escalation"],
    )
    assert len(concepts) == 3
    assert len({item["angle"] for item in concepts}) == 3
    assert all(item["source_expression_allowed"] is False for item in concepts)


def test_builds_render_blocked_30_second_plan_with_natural_clip_handles() -> None:
    plan = build_original_content_plan(
        topic="elephant ground-vibration communication",
        brand_profile="animal_x",
        reusable_mechanics=["first-second mystery", "behavior-led reveal"],
        selected_concept_id="animal_x-concept-2",
        script_segments=segments(),
        bible=bible(),
        factual_notes=[
            {
                "claim": "Elephants can detect low-frequency ground vibrations.",
                "source_url": "https://example.org/authoritative-source",
                "review_status": "pending_human_fact_review",
            }
        ],
        source_phrases=["A completely different source sentence not reused here."],
    )
    assert plan["validation"] == {"passed": True, "errors": []}
    assert len(plan["shots"]) == 6
    assert sum(shot["duration_seconds"] for shot in plan["shots"]) == 30
    assert all(shot["transition_handle_seconds"] >= 0.5 for shot in plan["shots"])
    assert all("Subject lock:" in shot["clip_prompt"] for shot in plan["shots"])
    assert all("identity drift" in shot["negative_prompt"] for shot in plan["shots"])
    assert plan["render_allowed"] is False
    assert plan["publish_allowed"] is False
    assert plan["human_review_required"] is True


def test_originality_distance_blocks_long_verbatim_source_expression() -> None:
    source = "these exact eight source words must never enter a new script unchanged"
    result = originality_distance(f"Opening line. {source}. Closing line.", [source])
    assert result["automated_check"] == "block"
    assert result["copied_long_phrases"] == [source]
