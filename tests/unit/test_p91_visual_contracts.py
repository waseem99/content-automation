from __future__ import annotations

from uuid import uuid4

import pytest

from src.application.visuals.adapters import (
    LocalKeyframeJobAdapter,
    LocalVisualCandidateContext,
    VisualPromptCompiler,
    candidate_seed,
)
from src.application.visuals.models import (
    CandidateCheck,
    CandidateCheckStatus,
    CandidateCheckType,
    CandidateResult,
    VisualProjectInitializeRequest,
)


def preset() -> dict:
    return {
        "palette": {"primary": "deep ocean blue", "accent": "warm coral"},
        "subject_rules": {"anatomy": "scientifically plausible octopus"},
        "environment_rules": {"location": "clear shallow reef"},
        "camera_rules": {"lens": "35mm", "movement": "locked frame"},
        "lighting_rules": {"direction": "soft top light"},
        "framing_rules": {"composition": "subject centered with safe text margins"},
        "negative_prompt": "illustration, cartoon",
        "exclusions": ["brand logos", "embedded text"],
    }


def references() -> list[dict]:
    return [
        {
            "id": uuid4(),
            "reference_key": "octopus-subject",
            "reference_type": "subject",
            "asset_id": uuid4(),
            "reference_fingerprint": "a" * 64,
            "description": "same red-brown octopus with one pale arm mark",
            "attributes": {"arm_mark": "pale crescent"},
            "active": True,
        }
    ]


def context(**overrides) -> LocalVisualCandidateContext:
    compiled = VisualPromptCompiler().compile(
        scene={"visual_brief": "An octopus arm explores a textured rock."},
        preset=preset(),
        references=references(),
    )
    values = {
        "portfolio_content_id": uuid4(),
        "content_version": 1,
        "production_workflow_id": uuid4(),
        "production_workflow_version_id": uuid4(),
        "script_version_id": uuid4(),
        "visual_project_id": uuid4(),
        "visual_shot_id": uuid4(),
        "visual_shot_version_id": uuid4(),
        "scene_plan_entry_id": uuid4(),
        "candidate_ordinal": 1,
        "seed": 911001,
        "provider": "comfyui-sdxl-local",
        "model_id": "sdxl-base-1.0",
        "width": 704,
        "height": 1280,
        "prompt": compiled.prompt,
        "negative_prompt": compiled.negative_prompt,
        "prompt_components": compiled.components,
        "reference_snapshot": compiled.reference_snapshot,
    }
    values.update(overrides)
    return LocalVisualCandidateContext(**values)


def passing_checks() -> list[CandidateCheck]:
    return [
        CandidateCheck(
            check_type=kind,
            status=CandidateCheckStatus.PASS,
            score=100,
            evidence={"deterministic_test": True},
            checked_by="p91-test-checker",
        )
        for kind in CandidateCheckType
    ]


def test_prompt_compiler_emits_all_components_and_reference_snapshot() -> None:
    compiled = VisualPromptCompiler().compile(
        scene={"visual_brief": "An octopus arm explores a textured rock."},
        preset=preset(),
        references=references(),
    )
    assert set(compiled.components) == {
        "subject", "action", "environment", "camera",
        "lighting", "palette", "framing", "exclusions",
    }
    assert "continuity references" in compiled.prompt
    assert "text" in compiled.negative_prompt
    assert compiled.reference_snapshot[0]["reference_key"] == "octopus-subject"


def test_local_keyframe_job_is_zero_fee_and_exact_version_bound() -> None:
    item = context()
    request = LocalKeyframeJobAdapter().build_enqueue(item, actor="producer.one")
    assert request.job_type.value == "keyframe"
    assert request.provider == "comfyui-sdxl-local"
    assert request.estimated_cost_usd == 0
    assert request.reserved_cost_usd == 0
    assert request.input_payload["visual_project_id"] == str(item.visual_project_id)
    assert request.input_payload["visual_shot_version_id"] == str(item.visual_shot_version_id)
    assert request.input_payload["seed"] == item.seed
    assert request.input_payload["billing"]["external_fee_allowed"] is False
    assert len(request.input_payload["output_contract"]["checks_required"]) == 10


def test_nonlocal_provider_is_rejected() -> None:
    with pytest.raises(ValueError, match="local ComfyUI"):
        LocalKeyframeJobAdapter().build_enqueue(
            context(provider="paid-cloud-image"),
            actor="producer.one",
        )


def test_candidate_seeds_are_distinct_by_shot_and_ordinal() -> None:
    assert candidate_seed(910000, shot_sequence=1, ordinal=1) == 911001
    assert candidate_seed(910000, shot_sequence=1, ordinal=2) == 911002
    assert candidate_seed(910000, shot_sequence=2, ordinal=1) == 912001


def test_candidate_result_requires_all_ten_checks_exactly_once() -> None:
    result = CandidateResult(
        asset_id=uuid4(),
        width=704,
        height=1280,
        provenance={"workflow_digest": "b" * 64},
        checks=passing_checks(),
    )
    assert len(result.checks) == 10

    with pytest.raises(ValueError, match="ten check types"):
        CandidateResult(
            asset_id=uuid4(),
            width=704,
            height=1280,
            provenance={"workflow_digest": "c" * 64},
            checks=passing_checks()[:-1],
        )


def test_visual_project_request_requires_at_least_three_portrait_candidates() -> None:
    request = VisualProjectInitializeRequest(visual_preset_id=uuid4())
    assert request.candidate_count == 3
    assert request.height > request.width
    with pytest.raises(ValueError, match="greater than or equal to 3"):
        VisualProjectInitializeRequest(visual_preset_id=uuid4(), candidate_count=2)
    with pytest.raises(ValueError, match="portrait"):
        VisualProjectInitializeRequest(visual_preset_id=uuid4(), width=1280, height=704)
