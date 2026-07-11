from __future__ import annotations

import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs" / "operations" / "p68-step-01.md"
BENCHMARK = ROOT / "docs" / "operations" / "p68-quality-benchmark.json"
HARNESS = ROOT / ".github" / "workflows" / "p1-acceptance-harness.yml"


def load_benchmark() -> dict[str, object]:
    return json.loads(BENCHMARK.read_text(encoding="utf-8"))


def test_p68_quality_benchmark_has_stable_identity_and_acceptance_gates() -> None:
    benchmark = load_benchmark()
    assert benchmark["schema_version"] == "p68.quality_benchmark.v1"
    assert benchmark["status"] == "contract_only_pending_pilot_evidence"
    assert benchmark["planned_epic"] == "P68"
    assert benchmark["parent_issue"] == 714
    assert benchmark["implementation_issue"] == 715

    acceptance = benchmark["acceptance"]
    assert acceptance["minimum_weighted_score"] == 8.0
    assert acceptance["minimum_dimension_score"] == 7
    assert acceptance["minimum_hard_gate_score"] == 8
    assert acceptance["human_approval_required"] is True
    assert acceptance["publish_allowed_by_default"] is False
    assert acceptance["source_media_allowed_in_render"] is False


def test_p68_quality_weights_total_one_hundred_and_hard_gates_are_present() -> None:
    dimensions = load_benchmark()["dimensions"]
    assert sum(item["weight"] for item in dimensions) == 100
    assert all(0 <= item["minimum_score"] <= 10 for item in dimensions)

    hard_gates = {item["id"] for item in dimensions if item["hard_gate"]}
    assert hard_gates == {
        "factual_accuracy_and_evidence",
        "rights_and_source_handling",
        "originality_distance",
        "advertiser_suitability",
    }


def test_p68_production_profile_and_reference_pack_are_measurable() -> None:
    benchmark = load_benchmark()
    profile = benchmark["production_profile"]
    assert (profile["width"], profile["height"], profile["fps"]) == (1080, 1920, 30)
    assert profile["duration_seconds"] == {"minimum": 25, "maximum": 38}
    assert profile["shot_count"] == {"minimum": 6, "maximum": 8}
    assert profile["minimum_clip_handle_seconds"] >= 0.5
    assert profile["target_loudness_lufs"] == -14
    assert profile["true_peak_ceiling_dbtp"] == -1

    reference_pack = benchmark["reference_pack"]
    assert reference_pack["minimum_direct_video_references_per_brand"] == 3
    assert reference_pack["required_rights_declaration"] is True
    assert reference_pack["source_media_retention"] == "temporary_local_analysis_only"
    assert "excluded_source_specific_elements" in reference_pack["required_fields"]


def test_p68_natural_clip_continuity_contract_blocks_transition_camouflage() -> None:
    benchmark = load_benchmark()
    continuity = set(benchmark["natural_continuity_checks"])
    assert {
        "subject_identity_consistency",
        "screen_direction_consistency",
        "camera_motion_compatibility",
        "action_overlap_or_pose_bridge",
        "first_and_last_frame_compatibility",
        "audio_ambience_continuity",
        "transition_is_story_motivated",
    }.issubset(continuity)

    assert set(benchmark["allowed_transition_strategies"]) == {
        "direct_cut",
        "match_cut",
        "action_cut",
        "j_cut",
        "l_cut",
        "brief_crossfade_under_300ms",
    }
    assert "flashy_transition_used_to_hide_unrelated_clips" in benchmark[
        "disallowed_shortcuts"
    ]


def test_p68_brand_profiles_reject_current_placeholder_quality() -> None:
    profiles = load_benchmark()["brand_profiles"]
    assert set(profiles) == {"rawr_nation", "animal_x"}
    assert "flat template-only diagrams" in profiles["rawr_nation"]["avoid"]
    assert "cartoon-only placeholder visuals" in profiles["animal_x"]["avoid"]
    assert "unverified sensationalism" in profiles["rawr_nation"]["avoid"]
    assert "invented scientific claims" in profiles["animal_x"]["avoid"]


def test_p68_step_01_documents_scope_clips_guardrails_and_sequence() -> None:
    content = DOC.read_text(encoding="utf-8")
    for term in [
        "Part of #714. Closes #715 after the PR merges.",
        "The P67 samples are technical proofs.",
        "A technically valid MP4 is not automatically a production candidate.",
        "at least three authorized direct-video references",
        "generate short clips and stitch them",
        "continuity plan is created before generation",
        "at least 0.5 seconds of usable transition handle",
        "J-cuts",
        "L-cuts",
        "brief crossfades under 300 ms",
        "Flashy transitions must not be used",
        "three for `rawr_nation`",
        "three for `animal_x`",
        "no cartoon-only placeholder visuals",
        "P68-05 generates or accepts short clips and stitches them naturally.",
        "publish_allowed: false",
    ]:
        assert term in content


def test_p68_tests_are_attached_to_acceptance_harness() -> None:
    workflow = HARNESS.read_text(encoding="utf-8")
    assert "tests/integration/test_p68_step_*.py" in workflow
