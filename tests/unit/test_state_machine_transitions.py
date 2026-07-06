import pytest

from src.application.state_machine import STAGE_TRANSITIONS, WORKFLOW_TRANSITIONS
from src.domain.workflow_status import StageStatus, WorkflowStatus


def test_workflow_transition_matrix_allows_expected_paths() -> None:
    assert WorkflowStatus.BLOCKED in WORKFLOW_TRANSITIONS[WorkflowStatus.ACTIVE]
    assert WorkflowStatus.COMPLETED in WORKFLOW_TRANSITIONS[WorkflowStatus.ACTIVE]
    assert WorkflowStatus.ACTIVE in WORKFLOW_TRANSITIONS[WorkflowStatus.FAILED]
    assert WORKFLOW_TRANSITIONS[WorkflowStatus.ARCHIVED] == set()


def test_workflow_transition_matrix_rejects_terminal_reactivation() -> None:
    assert WorkflowStatus.ACTIVE not in WORKFLOW_TRANSITIONS[WorkflowStatus.COMPLETED]
    assert WorkflowStatus.ACTIVE not in WORKFLOW_TRANSITIONS[WorkflowStatus.CANCELLED]


def test_stage_transition_matrix_allows_retry_and_human_review_paths() -> None:
    assert StageStatus.RUNNING in STAGE_TRANSITIONS[StageStatus.FAILED]
    assert StageStatus.COMPLETED in STAGE_TRANSITIONS[StageStatus.AWAITING_HUMAN]
    assert StageStatus.NEEDS_REVISION in STAGE_TRANSITIONS[StageStatus.AWAITING_HUMAN]


def test_stage_transition_matrix_rejects_completed_to_running_directly() -> None:
    assert StageStatus.RUNNING not in STAGE_TRANSITIONS[StageStatus.COMPLETED]
    assert STAGE_TRANSITIONS[StageStatus.SUPERSEDED] == set()
