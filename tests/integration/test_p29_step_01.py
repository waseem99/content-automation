from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.editorial_status import (
    ALLOWED_TRANSITIONS,
    BLOCKER_TYPES,
    EDITORIAL_STATUS_SCHEMA_VERSION,
    EDITORIAL_STATUSES,
    REQUIRED_GATE_FIELDS,
    build_editorial_status_model,
    evaluate_status_transition,
    required_gates_passed,
    validate_editorial_status_model,
)


pytestmark = pytest.mark.integration

DOC_PATH = Path("docs/operations/p29-step-01.md")
EXAMPLE_PATH = Path("docs/operations/p29-editorial-status-example.json")

PASSING_GATES = {
    "editorial_gate_passed": True,
    "rights_gate_passed": True,
    "p26_publish_block_clear": True,
    "source_attribution_complete": True,
    "monetization_review_passed": True,
}


def test_p29_step_01_documentation_covers_issue_scope() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for term in [
        "Part of #331. Closes #362 after the PR merges.",
        "editorial status lifecycle",
        "approval gates",
        "Allowed transitions",
        "Blocked and revision-required states",
        "P26 alignment",
        "src/editorial_status.py",
        "tests/integration/test_p29_step_01.py",
    ]:
        assert term in content


def test_p29_step_01_documentation_lists_required_statuses_and_blockers() -> None:
    content = DOC_PATH.read_text(encoding="utf-8")

    for status in EDITORIAL_STATUSES:
        assert status in content
    for blocker in BLOCKER_TYPES:
        assert blocker in content
    for gate in REQUIRED_GATE_FIELDS:
        assert gate in content

    for guardrail in [
        "build a review UI",
        "upload content to platforms",
        "publish content automatically",
        "store platform credentials or secrets",
        "treat `approved` as direct publish permission",
        "approve content while P26 publish blocks are active",
        "skip rights review",
        "skip source attribution review",
        "skip monetization review",
        "bypass workflow gates",
    ]:
        assert guardrail in content


def test_build_editorial_status_model_required_shape() -> None:
    model = build_editorial_status_model()

    assert model["schema_version"] == EDITORIAL_STATUS_SCHEMA_VERSION
    assert model["parent_epic"] == 331
    assert model["content_type"] == "editorial_status_model"
    assert [status["status"] for status in model["statuses"]] == list(EDITORIAL_STATUSES)
    assert set(model["allowed_transitions"]) == set(EDITORIAL_STATUSES)
    assert model["publish_allowed"] is False
    assert model["review_required"] is True


def test_editorial_status_model_transitions_and_readiness_flags() -> None:
    model = build_editorial_status_model()

    for status, next_statuses in ALLOWED_TRANSITIONS.items():
        assert model["allowed_transitions"][status] == list(next_statuses)

    for status_entry in model["statuses"]:
        assert status_entry["direct_platform_upload_allowed"] is False
        if status_entry["status"] == "publish_export_ready":
            assert status_entry["can_move_to_publish_export"] is True
        else:
            assert status_entry["can_move_to_publish_export"] is False


def test_editorial_status_model_gates_blockers_and_p26_alignment() -> None:
    model = build_editorial_status_model()

    approval_gates = model["approval_gates"]
    assert set(REQUIRED_GATE_FIELDS) <= set(approval_gates["required_for_publish_export_ready"])
    assert "P26 publish-block gates are clear" in approval_gates["rule"]

    blocked_states = model["blocked_states"]
    assert "revisions_required" in blocked_states
    assert "p26_publish_block" in blocked_states
    assert set(BLOCKER_TYPES) <= set(blocked_states["revisions_required"]["allowed_blocker_types"])
    assert "approved" in blocked_states["p26_publish_block"]["must_clear_before"]
    assert "publish_export_ready" in blocked_states["p26_publish_block"]["must_clear_before"]

    p26 = model["p26_alignment"]
    assert p26["p26_publish_block_clear_required"] is True
    assert p26["blocked_content_cannot_be_approved"] is True
    assert p26["blocked_content_cannot_be_publish_export_ready"] is True
    assert p26["risk_review_must_remain_visible"] is True


def test_required_gates_passed_only_when_all_required_gates_are_true() -> None:
    assert required_gates_passed(PASSING_GATES) is True

    for gate in REQUIRED_GATE_FIELDS:
        gates = dict(PASSING_GATES)
        gates[gate] = False
        assert required_gates_passed(gates) is False


def test_evaluate_status_transition_allows_gated_publish_export_ready_transition() -> None:
    result = evaluate_status_transition(
        "approved",
        "publish_export_ready",
        gates=PASSING_GATES,
    )

    assert result["schema_version"] == "p29.editorial_transition_evaluation.v1"
    assert result["transition_allowed"] is True
    assert result["transition_allowed_by_graph"] is True
    assert result["publish_allowed"] is False
    assert result["review_required"] is True
    assert result["errors"] == []


def test_evaluate_status_transition_blocks_publish_export_when_gates_missing() -> None:
    gates = dict(PASSING_GATES)
    gates["rights_gate_passed"] = False
    gates["p26_publish_block_clear"] = False

    result = evaluate_status_transition(
        "approved",
        "publish_export_ready",
        gates=gates,
    )

    assert result["transition_allowed"] is False
    assert "rights gate must pass" in result["errors"]
    assert "P26 publish block must be clear" in result["errors"]


def test_evaluate_status_transition_blocks_approval_when_content_has_blockers() -> None:
    result = evaluate_status_transition(
        "editorial_review",
        "approved",
        gates=PASSING_GATES,
        blockers=["editorial_changes_required"],
    )

    assert result["transition_allowed"] is False
    assert "blocked content cannot move to approval or publish-export states" in result["errors"]


def test_evaluate_status_transition_blocks_invalid_lifecycle_jump() -> None:
    result = evaluate_status_transition(
        "draft",
        "publish_export_ready",
        gates=PASSING_GATES,
    )

    assert result["transition_allowed"] is False
    assert result["transition_allowed_by_graph"] is False
    assert "transition is not allowed by lifecycle graph" in result["errors"]


def test_validate_editorial_status_model_accepts_generated_model() -> None:
    model = build_editorial_status_model()
    result = validate_editorial_status_model(model)

    assert result["schema_version"] == "p29.editorial_status_validation.v1"
    assert result["is_valid"] is True
    assert result["statuses_checked"] == list(EDITORIAL_STATUSES)
    assert result["gate_fields_checked"] == list(REQUIRED_GATE_FIELDS)
    assert result["blocker_types_checked"] == list(BLOCKER_TYPES)
    assert result["publish_allowed"] is False
    assert result["review_required"] is True
    assert result["errors"] == []


def test_validate_editorial_status_model_catches_missing_required_status() -> None:
    model = build_editorial_status_model()
    model["statuses"] = [status for status in model["statuses"] if status["status"] != "rights_review"]

    result = validate_editorial_status_model(model)

    assert result["is_valid"] is False
    assert "required editorial statuses missing or out of order" in result["errors"]


def test_validate_editorial_status_model_catches_publish_permission_regression() -> None:
    model = build_editorial_status_model()
    model["publish_allowed"] = True
    model["statuses"][0]["direct_platform_upload_allowed"] = True
    model["statuses"][0]["can_move_to_publish_export"] = True

    result = validate_editorial_status_model(model)

    assert result["is_valid"] is False
    assert "publish_allowed must remain false" in result["errors"]
    assert "direct platform upload must remain false" in result["errors"]
    assert "draft must not imply publish-export readiness" in result["errors"]


def test_validate_editorial_status_model_catches_p26_alignment_regression() -> None:
    model = build_editorial_status_model()
    model["p26_alignment"]["p26_publish_block_clear_required"] = False
    model["p26_alignment"]["blocked_content_cannot_be_approved"] = False
    model["p26_alignment"]["blocked_content_cannot_be_publish_export_ready"] = False

    result = validate_editorial_status_model(model)

    assert result["is_valid"] is False
    assert "P26 publish-block clear flag required" in result["errors"]
    assert "blocked content approval rule required" in result["errors"]
    assert "blocked content export rule required" in result["errors"]


def test_p29_editorial_status_example_is_valid() -> None:
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    result = validate_editorial_status_model(example)

    assert result["is_valid"] is True
    assert example["schema_version"] == EDITORIAL_STATUS_SCHEMA_VERSION
    assert [status["status"] for status in example["statuses"]] == list(EDITORIAL_STATUSES)
    assert example["publish_allowed"] is False
    assert example["review_required"] is True


def test_editorial_status_model_output_is_deterministic() -> None:
    first = build_editorial_status_model()
    second = build_editorial_status_model()

    assert first == second
