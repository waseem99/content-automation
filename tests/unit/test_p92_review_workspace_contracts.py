from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.application.review_workspace.models import (
    CommentType,
    InboxFilters,
    ReviewCommentRequest,
    ReviewTarget,
    RevisionTaskRequest,
    TaskMutationRequest,
    TaskType,
)


def test_change_request_requires_structured_task() -> None:
    with pytest.raises(ValidationError, match="structured revision task"):
        ReviewCommentRequest(
            target_type=ReviewTarget.SCRIPT_VERSION,
            target_id=uuid4(),
            comment_type=CommentType.CHANGE_REQUEST,
            body="Revise the script.",
            blocking=True,
        )


def test_timed_comments_require_exact_audio_mix() -> None:
    with pytest.raises(ValidationError, match="exact audio mix"):
        ReviewCommentRequest(
            target_type=ReviewTarget.SCRIPT_VERSION,
            target_id=uuid4(),
            comment_type=CommentType.TIMING,
            body="Timing note.",
            timeline_start_ms=100,
            timeline_end_ms=500,
        )


def test_task_mutation_changes_exactly_one_dimension() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        TaskMutationRequest(
            expected_lock_version=1,
            status="in_progress",
            priority="high",
        )


def test_due_window_cannot_be_reversed() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError, match="due_to"):
        InboxFilters(due_from=now, due_to=now.replace(year=now.year - 1))


def test_valid_change_request_contract() -> None:
    request = ReviewCommentRequest(
        target_type=ReviewTarget.VISUAL_SHOT_VERSION,
        target_id=uuid4(),
        comment_type=CommentType.CHANGE_REQUEST,
        body="Adjust the subject framing and preserve the landmark.",
        blocking=True,
        revision_task=RevisionTaskRequest(
            task_type=TaskType.VISUAL_PROMPT,
            title="Revise shot framing",
            instructions="Create a child prompt version and retain prior candidates.",
            assignee_operator_id="producer.one",
        ),
    )
    assert request.revision_task is not None
    assert request.blocking is True
